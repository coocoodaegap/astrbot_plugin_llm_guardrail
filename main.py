"""AstrBot LLM Guardrail plugin."""

import json
import time
import uuid
from pathlib import Path
from typing import Any

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import LLMResponse, ProviderRequest
from astrbot.api.star import Context, Star, register

try:
    from astrbot.api.star import StarTools
except ImportError:  # pragma: no cover - older SDKs and isolated unit tests.
    StarTools = None

try:
    from .access_control import (
        DECISION_BAN,
        DECISION_PARDON,
        REASON_MANUAL_COMMAND,
        AccessControlService,
        make_principal_identity,
    )
    from .adapters import AstrBotAdapter, ROUTE_SELECTED_PROVIDER_EXTRA
    from .config import resolve_session_scope
    from .constants import (
        GUARDRAIL_ACCESS_GATE_PRIORITY,
        GUARDRAIL_REQUEST_PRIORITY,
        GUARDRAIL_RESPONSE_PRIORITY,
        GUARDRAIL_WAITING_RAILS_PRIORITY,
        INTERNAL_MARKER,
    )
    from .rails import GuardrailPipeline, OUTPUT_HISTORY_DIRECTIVE_EXTRA_KEY
    from .pages_api import GuardrailPagesApiMixin
    from .rag_experience import RagExperienceService
    from .session_policy_state import SessionPolicyStateService
    from .session_lock import UmoLockManager, get_global_umo_lock_manager
    from .snapshots import ConfigSnapshotManager
    from .state import AstrBotKvStateStore, MemoryStateStore, StateStore
except ImportError:  # pragma: no cover - fallback for direct script loading
    from access_control import (
        DECISION_BAN,
        DECISION_PARDON,
        REASON_MANUAL_COMMAND,
        AccessControlService,
        make_principal_identity,
    )
    from adapters import AstrBotAdapter, ROUTE_SELECTED_PROVIDER_EXTRA
    from config import resolve_session_scope
    from constants import (
        GUARDRAIL_ACCESS_GATE_PRIORITY,
        GUARDRAIL_REQUEST_PRIORITY,
        GUARDRAIL_RESPONSE_PRIORITY,
        GUARDRAIL_WAITING_RAILS_PRIORITY,
        INTERNAL_MARKER,
    )
    from rails import GuardrailPipeline, OUTPUT_HISTORY_DIRECTIVE_EXTRA_KEY
    from pages_api import GuardrailPagesApiMixin
    from rag_experience import RagExperienceService
    from session_policy_state import SessionPolicyStateService
    from session_lock import UmoLockManager, get_global_umo_lock_manager
    from snapshots import ConfigSnapshotManager
    from state import AstrBotKvStateStore, MemoryStateStore, StateStore


PLUGIN_NAME = "astrbot_plugin_llm_guardrail"
PLUGIN_VERSION = "0.6.1"
POLICY_RUN_ID_EXTRA = "_llm_guardrail_policy_run_id"
POLICY_RUN_STARTED_AT_EXTRA = "_llm_guardrail_policy_run_started_at"
ACCESS_GATE_CHECKED_EXTRA = "_llm_guardrail_access_gate_checked"
ACCESS_GATE_BLOCKED_EXTRA = "_llm_guardrail_access_gate_blocked"
ACCESS_COMMAND_DEFAULT_LIMIT = 20
ACCESS_COMMAND_MAX_LIMIT = 100
POLICY_COMMAND_DEFAULT_LIMIT = 20
POLICY_COMMAND_MAX_LIMIT = 100

_PHASE_RAILS: dict[str, tuple[str, ...]] = {
    "message_input": ("input_rail",),
    "message_route": ("routing_rail",),
    "request": ("request_rail", "prompt_rail"),
    "response": ("output_rail",),
}
_LOGGING_PHASE_RAILS: dict[str, tuple[str, ...]] = {
    **_PHASE_RAILS,
    "access_gate": ("input_rail",),
    "waiting_rails": ("input_rail", "routing_rail"),
}
_LOG_NODE_DISPLAY_LIMIT = 10


def _format_log_node_ids(node_ids: list[str]) -> str:
    """Bound a node list while retaining terminal graph nodes at its tail."""

    if len(node_ids) <= _LOG_NODE_DISPLAY_LIMIT:
        return ",".join(node_ids) or "-"
    visible_count = _LOG_NODE_DISPLAY_LIMIT - 1
    hidden_count = len(node_ids) - visible_count
    return ",".join([f"...(+{hidden_count})", *node_ids[-visible_count:]])


@register(
    name=PLUGIN_NAME,
    author="Coocoodaegap",
    desc="LLM Guardrail Orchestrator: dynamic prompt injection, output checks, anti-injection, and model routing.",
    version=PLUGIN_VERSION,
    repo="https://github.com/coocoodaegap/astrbot_plugin_llm_guardrail",
)
class LlmGuardrailPlugin(GuardrailPagesApiMixin, Star):
    """LLM guardrail orchestrator."""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.context = context
        self.config = config
        self.adapter = AstrBotAdapter(context)
        self.snapshot_manager = ConfigSnapshotManager(
            config,
            persistence_path=self._snapshot_path(),
        )
        self.normalized_config = self.snapshot_manager.current.runtime_config
        self.umo_locks: UmoLockManager = get_global_umo_lock_manager()
        self.state_store: StateStore = self._build_state_store()
        self.access_control = AccessControlService(self.state_store)
        self.session_policy_state = SessionPolicyStateService(self.state_store)
        self.rag_experience = RagExperienceService(self.state_store)
        self.pipeline = GuardrailPipeline(
            self.normalized_config,
            self.adapter,
            access_control=self.access_control,
            rag_experience=self.rag_experience,
        )
        self._register_pages_web_api()

    async def initialize(self) -> None:
        """Initialize the plugin."""
        self.normalized_config = self.snapshot_manager.current.runtime_config
        self.pipeline = GuardrailPipeline(
            self.normalized_config,
            self.adapter,
            access_control=self.access_control,
            rag_experience=self.rag_experience,
        )
        logger.info(
            "[LLMGuardrail] loaded P3 v%s | warnings=%s",
            PLUGIN_VERSION,
            len(self.normalized_config.warnings),
        )

    @filter.on_waiting_llm_request(priority=GUARDRAIL_ACCESS_GATE_PRIORITY)
    async def guardrail_access_gate(
        self, event: AstrMessageEvent, *_args, **_kwargs
    ) -> None:
        """在其他等待阶段插件之前拦截被封禁主体。"""
        if not self or not getattr(self, "normalized_config", None):
            return
        try:
            async with self.umo_locks.hold(self.adapter.get_umo(event)):
                rail_context = await self._pipeline_for_event(event).run_access_gate(event)
                self.adapter.set_event_extra(event, ACCESS_GATE_CHECKED_EXTRA, True)
                if rail_context.input_blocked:
                    self.adapter.set_event_extra(event, ACCESS_GATE_BLOCKED_EXTRA, True)
                    await self._record_session_policy_state(
                        "message_input",
                        event,
                        rail_context,
                    )
        except Exception as exc:
            logger.error("[LLMGuardrail] access gate failed: %s", exc, exc_info=True)
            return
        if rail_context.input_blocked:
            self._log_context_summary("access_gate", rail_context)

    @filter.on_waiting_llm_request(priority=GUARDRAIL_WAITING_RAILS_PRIORITY)
    async def guardrail_waiting_rails(
        self, event: AstrMessageEvent, *_args, **_kwargs
    ) -> None:
        """在同一低优先级临界区依次执行输入分析和模型路由。"""
        if not self or not getattr(self, "normalized_config", None):
            return
        if self.adapter.get_event_extra(event, ACCESS_GATE_BLOCKED_EXTRA, False):
            return
        try:
            async with self.umo_locks.hold(self.adapter.get_umo(event)):
                pipeline = self._pipeline_for_event(event)
                access_already_checked = bool(
                    self.adapter.get_event_extra(
                        event,
                        ACCESS_GATE_CHECKED_EXTRA,
                        False,
                    )
                )
                input_context = await pipeline.run_message_input(
                    event,
                    access_already_checked=access_already_checked,
                )
                await self._record_session_policy_state(
                    "message_input",
                    event,
                    input_context,
                )
                if input_context.input_blocked:
                    rail_context = input_context
                else:
                    rail_context = await pipeline.run_message_route(
                        event,
                        access_already_checked=access_already_checked,
                        llm_request_confirmed=True,
                    )
                    await self._record_session_policy_state(
                        "message_route",
                        event,
                        rail_context,
                    )
        except Exception as exc:
            logger.error("[LLMGuardrail] waiting rails failed: %s", exc, exc_info=True)
            return
        self._log_context_summary("waiting_rails", rail_context)

    @filter.on_llm_request(priority=GUARDRAIL_REQUEST_PRIORITY)
    async def on_llm_request(
        self, event: AstrMessageEvent, req: ProviderRequest, *_args, **_kwargs
    ) -> None:
        """主模型调用前执行最终请求检查与提示词变更。"""
        if not self or not getattr(self, "normalized_config", None):
            return
        if self._is_internal_request(req):
            return
        try:
            async with self.umo_locks.hold(self.adapter.get_umo(event)):
                rail_context = await self._pipeline_for_event(event).run_request(event, req)
                await self._record_session_policy_state(
                    "request",
                    event,
                    rail_context,
                    request=req,
                )
        except Exception as exc:
            logger.error("[LLMGuardrail] request pipeline failed: %s", exc, exc_info=True)
            return
        self._log_context_summary("request", rail_context)

    @filter.on_llm_response(priority=GUARDRAIL_RESPONSE_PRIORITY)
    async def on_llm_response(
        self, event: AstrMessageEvent, resp: LLMResponse, *_args, **_kwargs
    ) -> None:
        """在模型回复发送前执行输出护栏。"""
        if not self or not getattr(self, "normalized_config", None):
            return
        try:
            async with self.umo_locks.hold(self.adapter.get_umo(event)):
                rail_context = await self._pipeline_for_event(event).run_response(event, resp)
                # ``run_response`` deliberately bypasses Output Rail work for
                # streaming chunks.  Do not let those no-op callbacks replace
                # the terminal result or fill the monitor activity log.
                if not bool(getattr(resp, "is_chunk", False)):
                    await self._record_session_policy_state(
                        "response",
                        event,
                        rail_context,
                    )
        except Exception as exc:
            logger.error("[LLMGuardrail] response pipeline failed: %s", exc, exc_info=True)
            return
        self._log_context_summary("response", rail_context)

    @filter.on_agent_done(priority=GUARDRAIL_RESPONSE_PRIORITY)
    async def on_agent_done(
        self, event: AstrMessageEvent, run_context: Any, _resp: LLMResponse, *_args, **_kwargs
    ) -> None:
        """仅将通过输出审核的输出提交到对话记录中。"""

        if not self or not getattr(self, "normalized_config", None):
            return
        directive = self.adapter.get_event_extra(
            event, OUTPUT_HISTORY_DIRECTIVE_EXTRA_KEY, None
        )
        if not isinstance(directive, dict):
            return
        action = str(directive.get("action", "") or "")
        text = str(directive.get("text", "") or "")
        if action == "commit":
            result = self.adapter.replace_final_assistant_message(run_context, text)
            if result.success:
                return
            logger.error(
                "[LLMGuardrail] final Step 5 output cannot replace history source: %s",
                "; ".join(result.warnings),
            )
            # Never allow the rejected candidate to be saved merely because
            # the host runtime changed its internal history representation.
            sent = await self.adapter.send_text_result(event, text)
            stop_result = self.adapter.stop_event(event)
            if not sent.success:
                logger.error(
                    "[LLMGuardrail] failed to send accepted output after history sync failure: %s",
                    "; ".join(sent.warnings),
                )
            if not stop_result.success:
                logger.error(
                    "[LLMGuardrail] failed to stop event after history sync failure: %s",
                    "; ".join(stop_result.warnings),
                )
            return
        if action == "block":
            # The block text is sent directly, then the core event is stopped
            # so it neither sends the candidate nor writes it to history.
            sent = await self.adapter.send_text_result(event, text)
            stop_result = self.adapter.stop_event(event)
            if not sent.success:
                logger.error(
                    "[LLMGuardrail] failed to send Step 5 block reply: %s",
                    "; ".join(sent.warnings),
                )
            if not stop_result.success:
                logger.error(
                    "[LLMGuardrail] failed to stop Step 5 blocked event: %s",
                    "; ".join(stop_result.warnings),
                )

    @filter.command_group("guardrail")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def guardrail(self, event: AstrMessageEvent):
        """LLM Guardrail 管理指令组。"""

        # AstrBot 的指令组必须指定子指令；状态查询使用 `/guardrail status`。
        return

    @filter.permission_type(filter.PermissionType.ADMIN)
    @guardrail.command("status")
    async def guardrail_status(self, event: AstrMessageEvent):
        """查看当前 LLM Guardrail P3 状态。"""

        yield event.plain_result(self._guardrail_status_text(event))

    @filter.permission_type(filter.PermissionType.ADMIN)
    @guardrail.command("policies")
    async def guardrail_policies(
        self,
        event: AstrMessageEvent,
        limit: str = "",
    ):
        """列出当前命令会话可用的策略。"""

        parsed_limit, error = self._parse_policy_command_limit(limit)
        if error:
            yield event.plain_result(error)
            return
        umo = self.adapter.get_umo(event).strip()
        snapshot = self.snapshot_manager.current
        library = snapshot.policy_library
        usable_policies = library.usable_policies()
        policies = usable_policies[:parsed_limit]
        if not policies:
            yield event.plain_result("策略列表：当前没有可用策略。")
            return
        resolution = library.resolve_usable_policy_for_umo(umo)
        lines = [
            f"策略列表：显示 {len(policies)} 条可用策略",
            f"- 当前 UMO: {umo or '(不可用)'}",
        ]
        for policy in policies:
            labels: list[str] = []
            if policy.policy_id == resolution.explicit_policy_id:
                labels.append("已明确指定")
            if umo and umo in policy.umo_list:
                labels.append("匹配当前 UMO")
            if policy.policy_id == library.active_policy_id:
                labels.append("全局默认")
            label = f"（{'、'.join(labels)}）" if labels else ""
            lines.append(
                f"- {policy.policy_id}: {policy.name or policy.policy_id}{label}"
            )
        if len(usable_policies) > len(policies):
            lines.append("- 其余策略未显示；可用 /guardrail policies [limit] 调整数量。")
        yield event.plain_result("\n".join(lines))

    @filter.permission_type(filter.PermissionType.ADMIN)
    @guardrail.command("policy")
    async def guardrail_policy(
        self,
        event: AstrMessageEvent,
        policy_id: str = "",
        umo: str = "",
    ):
        """为当前或指定 UMO 选择策略。"""

        target = str(policy_id or "").strip()
        if not target:
            yield event.plain_result(
                "用法：/guardrail policy <policy_id> [umo]；使用 /guardrail policy --auto [umo] 恢复自动选路。"
            )
            return
        target_umo = str(umo or "").strip() or self.adapter.get_umo(event).strip()
        if not target_umo:
            yield event.plain_result("未提供目标 UMO，且无法取得当前 UMO，未修改策略指定。")
            return
        snapshot = self.snapshot_manager.current
        if target != "--auto" and not snapshot.policy_library.is_policy_usable(target):
            yield event.plain_result(
                f"策略“{target}”不存在或当前不可用，未修改当前 UMO 的策略指定。"
            )
            return
        result = await self.snapshot_manager.publish_umo_policy_selection(
            target_umo,
            None if target == "--auto" else target,
            expected_revision=snapshot.revision,
        )
        if result.conflict:
            yield event.plain_result("策略库已被其他操作更新，请重新执行该指令。")
            return
        if not result.success:
            detail = result.diagnostics[0] if result.diagnostics else "未知错误"
            yield event.plain_result(f"保存当前 UMO 的策略指定失败：{detail}")
            return
        if target == "--auto":
            yield event.plain_result(
                f"已取消 UMO “{target_umo}”的明确策略指定，后续请求恢复自动选路。"
            )
            return
        yield event.plain_result(
            f"已为 UMO “{target_umo}”明确指定策略“{target}”；后续请求将优先使用它。"
        )

    @filter.permission_type(filter.PermissionType.ADMIN)
    @guardrail.command("access")
    async def guardrail_access_list(
        self,
        event: AstrMessageEvent,
        decision: str = "",
        limit: str = "",
    ):
        """列出当前平台适配器命名空间内有效的封禁或赦免决定。"""

        filter_decision = str(decision or "").strip().lower()
        raw_limit = str(limit or "").strip()
        if filter_decision and filter_decision not in {DECISION_BAN, DECISION_PARDON}:
            if not raw_limit and self._looks_like_integer(filter_decision):
                raw_limit = filter_decision
                filter_decision = ""
            else:
                yield event.plain_result("用法：/guardrail access [ban|pardon] [limit]")
                return
        parsed_limit, error = self._parse_access_command_limit(raw_limit)
        if error:
            yield event.plain_result(error)
            return
        command_parts = self.adapter.get_principal_parts(event)
        if command_parts is None:
            yield event.plain_result("无法取得当前平台适配器名，未查询访问控制记录。")
            return
        result = await self.access_control.list_active_records()
        if not result.success:
            yield event.plain_result("访问控制状态暂不可用，请稍后重试。")
            return
        records = [
            record
            for record in result.records
            if record.get("platform_id") == command_parts[0]
            and (not filter_decision or record.get("decision") == filter_decision)
        ][:parsed_limit]
        label = {DECISION_BAN: "封禁", DECISION_PARDON: "赦免"}.get(
            filter_decision,
            "全部有效决定",
        )
        if not records:
            yield event.plain_result(f"访问控制：{label}（无记录）")
            return
        lines = [f"访问控制：{label}（显示 {len(records)} 条）"]
        lines.extend(self._format_access_record(record) for record in records)
        yield event.plain_result("\n".join(lines))

    @filter.permission_type(filter.PermissionType.ADMIN)
    @guardrail.command("accs")
    async def guardrail_access_status(self, event: AstrMessageEvent, user_id: str):
        """查看指定主体当前有效的访问决定。"""

        principal, error = self._access_command_principal(event, user_id)
        if error:
            yield event.plain_result(error)
            return
        record = await self.access_control.get_active_record(principal)
        if record is None:
            yield event.plain_result(
                f"访问控制：{principal.user_id} 当前没有有效决定。"
            )
            return
        yield event.plain_result(
            "访问控制：\n" + self._format_access_record(record, mask_user_id=False)
        )

    @filter.permission_type(filter.PermissionType.ADMIN)
    @guardrail.command("accb")
    async def guardrail_access_ban(
        self,
        event: AstrMessageEvent,
        user_id: str,
        minutes: str = "",
    ):
        """在当前平台适配器命名空间中创建或替换手动封禁。"""

        message = await self._set_access_command_decision(
            event,
            user_id,
            minutes,
            DECISION_BAN,
        )
        yield event.plain_result(message)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @guardrail.command("accp")
    async def guardrail_access_pardon(
        self,
        event: AstrMessageEvent,
        user_id: str,
        minutes: str = "",
    ):
        """在当前平台适配器命名空间中创建或替换手动赦免。"""

        message = await self._set_access_command_decision(
            event,
            user_id,
            minutes,
            DECISION_PARDON,
        )
        yield event.plain_result(message)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @guardrail.command("accr")
    async def guardrail_access_release(self, event: AstrMessageEvent, user_id: str):
        """在比较并交换保护下清除当前有效的访问决定。"""

        principal, error = self._access_command_principal(event, user_id)
        if error:
            yield event.plain_result(error)
            return
        record = await self.access_control.get_active_record(principal)
        if record is None:
            yield event.plain_result("该主体当前没有有效封禁或赦免。")
            return
        result = await self.access_control.clear_manual_decision(
            principal,
            expected_decision=str(record["decision"]),
            expected_record_revision=int(record["record_revision"]),
        )
        if result.conflict:
            yield event.plain_result("访问决定已被其他管理员修改，请重新查询后再解除。")
            return
        if not result.success:
            yield event.plain_result("解除访问决定失败，请稍后重试。")
            return
        decision_label = "封禁" if record["decision"] == DECISION_BAN else "赦免"
        yield event.plain_result(
            f"已解除{decision_label}：{principal.user_id}。"
        )

    def _guardrail_status_text(self, event: AstrMessageEvent) -> str:
        """构建 ``/guardrail status`` 的状态响应。"""
        cfg = self.snapshot_manager.current.runtime_config
        current_umo = self.adapter.get_umo(event)
        session_decision = resolve_session_scope(
            cfg.session_control,
            current_umo,
            self.adapter.is_private_chat(event),
        )
        rail_lines = []
        for rail_name in (
            "input_rail",
            "routing_rail",
            "request_rail",
            "prompt_rail",
            "output_rail",
        ):
            rail = cfg.rails[rail_name]
            enabled_nodes = sum(1 for node in rail.nodes if node.enabled and node.valid)
            rail_lines.append(
                f"- {rail_name}: enabled={rail.enabled}, nodes={enabled_nodes}/{len(rail.nodes)}"
            )

        lines = [
            "LLM Guardrail P3",
            f"- version: {PLUGIN_VERSION}",
            f"- schema: {cfg.schema_version}",
            "- session scope: "
            f"group={cfg.session_control.get('group_chat_mode', 'all_run')}, "
            f"private={cfg.session_control.get('private_chat_mode', 'all_run')}",
            f"- current UMO: {current_umo or '(empty)'}",
            f"- current session action: {session_decision.action} ({session_decision.reason})",
            f"- warnings: {len(cfg.warnings)}",
            *rail_lines,
            "- capabilities: keywords, regex, logic gates, request checks, prompt mutations, first-hit routing, output blocking/sanitizing, bounded output retry",
        ]
        if cfg.warnings:
            lines.append("- first warning: " + self._clip_text(cfg.warnings[0], 160))
        return "\n".join(lines)

    async def _set_access_command_decision(
        self,
        event: AstrMessageEvent,
        user_id: str,
        minutes: str,
        decision: str,
    ) -> str:
        """Write one command-originated decision through AccessControlService."""

        principal, error = self._access_command_principal(event, user_id)
        if error:
            return error
        duration, error = self._parse_access_command_duration(minutes)
        if error:
            return error
        current = await self.access_control.get_active_record(principal)
        expected_revision = (
            int(current["record_revision"]) if current is not None else None
        )
        result = await self.access_control.set_manual_decision(
            principal,
            decision,
            duration,
            REASON_MANUAL_COMMAND,
            expected_record_revision=expected_revision,
        )
        if result.conflict:
            return "访问决定已被其他管理员修改，请重新执行指令。"
        if not result.success:
            return "保存访问决定失败，请稍后重试。"
        decision_label = "封禁" if decision == DECISION_BAN else "赦免"
        return (
            f"已{decision_label}：{principal.user_id}"
            f"（{self._format_access_expiry(result.record or {})}）。"
        )

    def _access_command_principal(
        self, event: AstrMessageEvent, user_id: str
    ) -> tuple[Any | None, str]:
        """Build an explicit target identity in the command event's adapter scope."""

        parts = self.adapter.get_principal_parts(event)
        if parts is None:
            return None, "无法取得当前平台适配器名，未执行访问控制操作。"
        try:
            return make_principal_identity(parts[0], user_id), ""
        except (TypeError, ValueError):
            return None, "user_id 无效。"

    @staticmethod
    def _looks_like_integer(value: str) -> bool:
        text = str(value or "").strip()
        return bool(text) and (text.isdigit() or (text.startswith("-") and text[1:].isdigit()))

    @classmethod
    def _parse_access_command_limit(cls, raw_limit: str) -> tuple[int, str]:
        text = str(raw_limit or "").strip()
        if not text:
            return ACCESS_COMMAND_DEFAULT_LIMIT, ""
        if not cls._looks_like_integer(text):
            return 0, "limit 必须是 1 到 100 的整数。"
        value = int(text)
        if value < 1 or value > ACCESS_COMMAND_MAX_LIMIT:
            return 0, "limit 必须是 1 到 100 的整数。"
        return value, ""

    @classmethod
    def _parse_policy_command_limit(cls, raw_limit: str) -> tuple[int, str]:
        text = str(raw_limit or "").strip()
        if not text:
            return POLICY_COMMAND_DEFAULT_LIMIT, ""
        if not cls._looks_like_integer(text):
            return 0, "limit 必须是 1 到 100 的整数。"
        value = int(text)
        if value < 1 or value > POLICY_COMMAND_MAX_LIMIT:
            return 0, "limit 必须是 1 到 100 的整数。"
        return value, ""

    @classmethod
    def _parse_access_command_duration(cls, raw_minutes: str) -> tuple[int, str]:
        text = str(raw_minutes or "").strip()
        if not text:
            return -1, ""
        if not cls._looks_like_integer(text):
            return 0, "minutes 必须为 -1 或正整数。"
        value = int(text)
        if value == 0 or value < -1:
            return 0, "minutes 必须为 -1 或正整数。"
        return value, ""

    @classmethod
    def _format_access_record(
        cls, record: dict[str, Any], *, mask_user_id: bool = True
    ) -> str:
        decision = str(record.get("decision", "") or "")
        decision_label = "封禁" if decision == DECISION_BAN else "赦免"
        platform_id = cls._mask_access_identifier(record.get("platform_id", ""))
        raw_user_id = str(record.get("user_id", ""))
        user_id = (
            cls._mask_access_identifier(raw_user_id) if mask_user_id else raw_user_id
        )
        reason = str(
            record.get("decision_reason_label", "")
            or record.get("decision_reason_code", "")
            or "未注明"
        )
        count = int(record.get("violation_count", 0) or 0)
        return (
            f"- {decision_label} {platform_id}/{user_id}"
            f" | 到期：{cls._format_access_expiry(record)}"
            f" | 计数：{count} | 原因：{reason}"
        )

    @staticmethod
    def _format_access_expiry(record: dict[str, Any]) -> str:
        try:
            expires_at = int(record.get("decision_expires_at", 0) or 0)
        except (TypeError, ValueError):
            return "未知"
        if expires_at <= 0:
            return "永久"
        return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(expires_at))

    @staticmethod
    def _mask_access_identifier(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return "***"
        if len(text) == 1:
            return "*"
        if len(text) <= 4:
            return text[0] + "*" * (len(text) - 2) + text[-1]
        return text[:2] + "…" + text[-2:]

    async def terminate(self) -> None:
        """Clean up plugin resources."""
        logger.info("[LLMGuardrail] stopped")

    def _pipeline_for_event(self, event: AstrMessageEvent) -> GuardrailPipeline:
        """Build a pipeline from the snapshot fixed to this request event."""

        snapshot = self.snapshot_manager.bind_event(self.adapter, event)
        _policy_id, runtime_config = snapshot.runtime_config_for_umo(
            self.adapter.get_umo(event)
        )
        return GuardrailPipeline(
            runtime_config,
            self.adapter,
            access_control=self.access_control,
            rag_experience=self.rag_experience,
        )

    def _ensure_policy_run(self, event: AstrMessageEvent) -> tuple[str, int]:
        """Attach one opaque execution correlation ID to the AstrBot event."""

        run_id = str(
            self.adapter.get_event_extra(event, POLICY_RUN_ID_EXTRA, "") or ""
        ).strip()
        if not run_id:
            run_id = uuid.uuid4().hex
            self.adapter.set_event_extra(event, POLICY_RUN_ID_EXTRA, run_id)
        raw_started_at = self.adapter.get_event_extra(
            event,
            POLICY_RUN_STARTED_AT_EXTRA,
            0,
        )
        try:
            started_at = int(raw_started_at)
        except (TypeError, ValueError):
            started_at = 0
        if started_at <= 0:
            started_at = int(time.time())
            self.adapter.set_event_extra(event, POLICY_RUN_STARTED_AT_EXTRA, started_at)
        return run_id, started_at

    async def _record_session_policy_state(
        self,
        phase: str,
        event: AstrMessageEvent,
        rail_context: Any,
        *,
        request: ProviderRequest | None = None,
    ) -> None:
        """Persist one P2-A observation without affecting the request path."""

        service = getattr(self, "session_policy_state", None)
        if service is None:
            return
        try:
            snapshot = self.snapshot_manager.bind_event(self.adapter, event)
            umo = self.adapter.get_umo(event)
            policy_id, _policy_runtime_config = snapshot.runtime_config_for_umo(umo)
            # Retention and enablement belong to the system-level monitor, not
            # to an individual policy (or the system fallback graph).  A
            # policy's graph can change, but monitoring remains consistently
            # enabled/disabled for every UMO.
            settings = snapshot.runtime_config.session_policy_state
            if not bool(settings.get("enabled", False)):
                return
            run_id, started_at = self._ensure_policy_run(event)
            route_candidate = self._route_candidate_observation(phase, rail_context)
            request_target = None
            if phase == "request" and request is not None:
                request_target = await self._request_target_observation(event, request)
            result = await service.record_phase(
                getattr(rail_context, "umo", umo),
                run_id=run_id,
                policy_id=policy_id,
                snapshot_revision=snapshot.revision,
                started_at=started_at,
                phase=phase,
                outcome=self._policy_outcome(rail_context),
                terminal_action=getattr(rail_context, "terminal_action", None),
                rail_outcomes=self._phase_rail_outcomes(phase, rail_context),
                signals=self._phase_signals(phase, rail_context),
                settings=settings,
                route_candidate=route_candidate,
                request_target_observation=request_target,
                retry_activities=self._phase_retry_activities(phase, rail_context),
            )
            if not result.success and result.warning:
                logger.warning(
                    "[LLMGuardrail] session-policy monitoring: %s",
                    result.warning,
                )
        except Exception as exc:  # Defensive boundary around an optional monitor.
            logger.warning(
                "[LLMGuardrail] session-policy monitoring failed: %s",
                exc,
            )
            return

    @staticmethod
    def _policy_outcome(rail_context: Any) -> str:
        if bool(getattr(rail_context, "input_blocked", False)) or bool(
            getattr(rail_context, "output_blocked", False)
        ):
            return "blocked"
        results = getattr(rail_context, "results", {})
        if not isinstance(results, dict) or not results:
            return "skipped"
        return "allowed"

    @staticmethod
    def _phase_rail_outcomes(phase: str, rail_context: Any) -> dict[str, dict[str, Any]]:
        results = getattr(rail_context, "results", {})
        if not isinstance(results, dict):
            results = {}
        terminal_action = getattr(rail_context, "terminal_action", None)
        terminal_rail = (
            str(terminal_action.get("rail", "") or "")
            if isinstance(terminal_action, dict)
            else ""
        )
        outcomes: dict[str, dict[str, Any]] = {}
        for rail_name in _PHASE_RAILS.get(phase, ()):
            rail_results = [
                result
                for result in results.values()
                if str(getattr(result, "rail", "") or "") == rail_name
            ]
            executed = [
                result for result in rail_results if bool(getattr(result, "executed", False))
            ]
            matched = [
                str(getattr(result, "node_id", "") or "")
                for result in executed
                if bool(getattr(result, "matched", False))
            ]
            outcome = "completed" if executed else "skipped"
            if terminal_rail == rail_name:
                outcome = "blocked"
            outcomes[rail_name] = {
                "outcome": outcome,
                "executed_node_count": len(executed),
                "matched_node_ids": matched,
            }
        if phase == "message_route":
            decision = getattr(rail_context, "route_decision", None)
            route_outcome = "abstained"
            if decision is not None:
                provider_id = str(getattr(decision, "provider_id", "") or "").strip()
                if not bool(getattr(decision, "applied", False)):
                    route_outcome = "invalid"
                elif provider_id:
                    route_result = getattr(rail_context, "results", {}).get(
                        getattr(decision, "source_node_id", ""),
                        None,
                    )
                    metadata = getattr(route_result, "metadata", {})
                    route_outcome = (
                        "invalid"
                        if isinstance(metadata, dict) and metadata.get("default_route")
                        else "selected"
                    )
            outcomes.setdefault("routing_rail", {})["route_outcome"] = route_outcome
        return outcomes

    @staticmethod
    def _phase_signals(phase: str, rail_context: Any) -> list[dict[str, Any]]:
        rails = set(_PHASE_RAILS.get(phase, ()))
        results = getattr(rail_context, "results", {})
        if not isinstance(results, dict):
            return []
        signals: list[dict[str, Any]] = []
        for result in results.values():
            if str(getattr(result, "rail", "") or "") not in rails:
                continue
            if not bool(getattr(result, "executed", False)) or not bool(
                getattr(result, "matched", False)
            ):
                continue
            signal = getattr(result, "signal", None)
            if signal is None:
                continue
            raw_signal = {
                "value": getattr(signal, "value", None),
                "truthy": bool(getattr(signal, "truthy", False)),
                "payload": getattr(signal, "payload", {}),
            }
            try:
                serialized_signal = json.loads(
                    json.dumps(raw_signal, ensure_ascii=False, allow_nan=False)
                )
            except (TypeError, ValueError):
                # A third-party node may emit an arbitrary Python object.  A
                # monitor failure must not interfere with the user request.
                continue
            signals.append(
                {
                    "rail": str(getattr(result, "rail", "") or ""),
                    "node_id": str(getattr(result, "node_id", "") or ""),
                    "user_node_id": str(
                        getattr(result, "user_node_id", "") or ""
                    ),
                    "template_key": str(
                        getattr(result, "template_key", "") or ""
                    ),
                    "signal": serialized_signal,
                }
            )
        return signals

    @staticmethod
    def _phase_retry_activities(phase: str, rail_context: Any) -> list[dict[str, Any]]:
        """Expose P3's compact retry audit entries only for the response phase."""

        if phase != "response":
            return []
        raw_trace = getattr(rail_context, "retry_trace", [])
        if not isinstance(raw_trace, list):
            return []
        entries: list[dict[str, Any]] = []
        for item in raw_trace:
            if not isinstance(item, dict):
                continue
            entries.append(
                {
                    "request_id": item.get("request_id", ""),
                    "node_id": item.get("node_id", ""),
                    "attempt": item.get("attempt", 0),
                    "max_retries": item.get("max_retries", 0),
                    "provider_id": item.get("provider_id", ""),
                    "provider_source": item.get("provider_source", ""),
                    "outcome": item.get("outcome", ""),
                    "elapsed_ms": item.get("elapsed_ms", 0),
                }
            )
        return entries

    def _route_candidate_observation(
        self,
        phase: str,
        rail_context: Any,
    ) -> dict[str, str] | None:
        if phase != "message_route":
            return None
        decision = getattr(rail_context, "route_decision", None)
        if decision is None or not bool(getattr(decision, "applied", False)):
            return None
        provider_id = str(getattr(decision, "provider_id", "") or "").strip()
        if not provider_id:
            # An empty route-policy target means "keep AstrBot default", not a
            # reusable Provider candidate.
            return None
        source_node_id = str(getattr(decision, "source_node_id", "") or "")
        route_result = getattr(rail_context, "results", {}).get(source_node_id)
        metadata = getattr(route_result, "metadata", {})
        if isinstance(metadata, dict) and metadata.get("default_route"):
            # apply_route() reports an unavailable Provider as successful while
            # intentionally falling back to AstrBot's default route.
            return None
        event = getattr(rail_context, "event", None)
        selected_provider = str(
            self.adapter.get_event_extra(event, ROUTE_SELECTED_PROVIDER_EXTRA, "")
            if event is not None
            else ""
        ).strip()
        if selected_provider != provider_id:
            # A route candidate represents a Provider target that Guardrail
            # actually submitted to AstrBot's request-selection path, not
            # merely the route node's configured intent.
            return None
        return {
            "provider_id": provider_id,
            "model_id": "",
            "source_route_node_id": source_node_id,
        }

    async def _request_target_observation(
        self,
        event: AstrMessageEvent,
        request: ProviderRequest,
    ) -> dict[str, str]:
        """Capture a request target without assuming undocumented SDK fields.

        Newer/third-party ProviderRequest implementations may expose direct
        ``provider_id`` and ``model`` attributes. When they do not, record the
        event's explicit ``selected_provider`` request selection, if present.
        The monitor never falls back to a UMO's session-default Provider.
        """

        provider_id = self._request_string_field(request, "provider_id")
        model_id = self._request_string_field(request, "model")
        if not model_id:
            model_id = self._request_string_field(request, "model_id")
        if provider_id or model_id:
            return {
                "provider_id": provider_id,
                "model_id": model_id,
                "source": "provider_request",
            }
        selected_provider = self.adapter.get_selected_request_provider_id(event)
        if selected_provider:
            return {
                "provider_id": selected_provider,
                "model_id": "",
                "source": "event_selected_provider",
            }
        return {
            "provider_id": "",
            "model_id": "",
            "source": "unavailable",
        }

    @staticmethod
    def _request_string_field(request: Any, name: str) -> str:
        try:
            value = getattr(request, name, "")
            if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                return str(value).strip()
        except Exception:
            return ""
        return ""

    def _build_state_store(self) -> StateStore:
        """Use AstrBot's plugin KV storage when the host exposes it."""

        required_methods = (
            "get_kv_data",
            "put_kv_data",
            "delete_kv_data",
        )
        if all(callable(getattr(self, method_name, None)) for method_name in required_methods):
            return AstrBotKvStateStore(self, prefix=PLUGIN_NAME)
        warning = getattr(logger, "warning", None)
        if callable(warning):
            warning(
                "[LLMGuardrail] AstrBot KV storage is unavailable; "
                "access-control state will not survive restart"
            )
        return MemoryStateStore()

    @staticmethod
    def _snapshot_path() -> Path | None:
        getter = getattr(StarTools, "get_data_dir", None)
        if not callable(getter):
            return None
        try:
            return Path(getter(PLUGIN_NAME)) / "config_snapshot.json"
        except (OSError, TypeError, ValueError) as exc:
            logger.warning("[LLMGuardrail] cannot resolve snapshot data directory: %s", exc)
            return None

    @staticmethod
    def _clip_text(text: object, limit: int = 120) -> str:
        value = str(text or "").replace("\n", " ").strip()
        if len(value) <= limit:
            return value
        return f"{value[:limit]}..."

    @staticmethod
    def _is_internal_request(req: ProviderRequest) -> bool:
        system_prompt = str(getattr(req, "system_prompt", "") or "")
        prompt = str(getattr(req, "prompt", "") or "")
        return INTERNAL_MARKER in system_prompt or INTERNAL_MARKER in prompt

    def _log_context_summary(self, phase: str, rail_context) -> None:
        if not self.normalized_config.debug_settings["logging"]:
            return
        phase_rails = _LOGGING_PHASE_RAILS.get(phase, ())
        phase_results = [
            result
            for result in rail_context.results.values()
            if not phase_rails or result.rail in phase_rails
        ]
        matched = [
            result.rule_id
            for result in phase_results
            if result.executed and result.matched
        ]
        executed = [
            result.rule_id
            for result in phase_results
            if result.executed
        ]
        errors = [
            result.rule_id
            for result in phase_results
            if result.executed and result.metadata.get("error")
        ]
        route_label = (
            rail_context.route_decision.provider_id
            if rail_context.route_decision
            else self.adapter.get_active_route_target(rail_context.event)
        )
        session_action = (
            rail_context.session_scope_decision.action
            if rail_context.session_scope_decision
            else "-"
        )
        snapshot = self.snapshot_manager.bind_event(self.adapter, rail_context.event)
        policy_id, _runtime_config = snapshot.runtime_config_for_umo(rail_context.umo)
        mutations = [
            ":".join(
                str(part)
                for part in (
                    item.get("kind", ""),
                    item.get("target", ""),
                    item.get("rule_id", ""),
                )
                if part
            )
            for item in rail_context.prompt_mutations
        ]
        logger.info(
            "[LLMGuardrail] %s | umo=%s | policy=%s | session=%s | executed=%s | matched=%s | errors=%s | input_blocked=%s | output_blocked=%s | route=%s | mutations=%s | warnings=%s | last_warning=%s",
            phase,
            rail_context.umo,
            policy_id,
            session_action,
            _format_log_node_ids(executed),
            _format_log_node_ids(matched),
            _format_log_node_ids(errors),
            rail_context.input_blocked,
            rail_context.output_blocked,
            route_label or "-",
            ",".join(mutations[:10]) or "-",
            len(rail_context.warnings),
            self._clip_text(rail_context.warnings[-1], 180)
            if rail_context.warnings
            else "-",
        )
