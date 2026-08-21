"""AstrBot LLM Guardrail plugin."""

from pathlib import Path

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import LLMResponse, ProviderRequest
from astrbot.api.star import Context, Star, register

try:
    from astrbot.api.star import StarTools
except ImportError:  # pragma: no cover - older SDKs and isolated unit tests.
    StarTools = None

try:
    from .adapters import AstrBotAdapter
    from .config import resolve_session_scope
    from .constants import (
        GUARDRAIL_MESSAGE_INPUT_PRIORITY,
        GUARDRAIL_MESSAGE_ROUTE_PRIORITY,
        INTERNAL_MARKER,
    )
    from .rails import GuardrailPipeline
    from .pages_api import GuardrailPagesApiMixin
    from .session_lock import UmoLockManager, get_global_umo_lock_manager
    from .snapshots import ConfigSnapshotManager
    from .state import MemoryStateStore, StateStore
except ImportError:  # pragma: no cover - fallback for direct script loading
    from adapters import AstrBotAdapter
    from config import resolve_session_scope
    from constants import (
        GUARDRAIL_MESSAGE_INPUT_PRIORITY,
        GUARDRAIL_MESSAGE_ROUTE_PRIORITY,
        INTERNAL_MARKER,
    )
    from rails import GuardrailPipeline
    from pages_api import GuardrailPagesApiMixin
    from session_lock import UmoLockManager, get_global_umo_lock_manager
    from snapshots import ConfigSnapshotManager
    from state import MemoryStateStore, StateStore


PLUGIN_NAME = "astrbot_plugin_llm_guardrail"
PLUGIN_VERSION = "0.1.0"
MESSAGE_STAGE_LOCK_EXTRA = "_llm_guardrail_message_stage_lock"


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
        self.pipeline = GuardrailPipeline(self.normalized_config, self.adapter)
        self.umo_locks: UmoLockManager = get_global_umo_lock_manager()
        self.state_store: StateStore = MemoryStateStore()
        self._register_pages_web_api()

    async def initialize(self) -> None:
        """Initialize the plugin."""
        self.normalized_config = self.snapshot_manager.current.runtime_config
        self.pipeline = GuardrailPipeline(self.normalized_config, self.adapter)
        logger.info(
            "[LLMGuardrail] loaded P1 v%s | warnings=%s",
            PLUGIN_VERSION,
            len(self.normalized_config.warnings),
        )

    @filter.event_message_type(
        filter.EventMessageType.ALL,
        priority=GUARDRAIL_MESSAGE_INPUT_PRIORITY,
    )
    async def guardrail_message_input(
        self, event: AstrMessageEvent, *_args, **_kwargs
    ) -> None:
        """Run user input checks before other ordinary message handlers."""
        if not self or not getattr(self, "normalized_config", None):
            return
        lease = await self.umo_locks.acquire(self.adapter.get_umo(event))
        lease_result = self.adapter.set_event_extra(event, MESSAGE_STAGE_LOCK_EXTRA, lease)
        keep_message_stage_lock = False
        try:
            rail_context = await self._pipeline_for_event(event).run_message_input(event)
            keep_message_stage_lock = (
                lease_result.success
                and self._should_keep_message_stage_lock(rail_context)
            )
        except Exception as exc:
            logger.error("[LLMGuardrail] message input pipeline failed: %s", exc, exc_info=True)
            return
        finally:
            if not keep_message_stage_lock:
                await lease.release()
        self._log_context_summary("message_input", rail_context)

    @filter.event_message_type(
        filter.EventMessageType.ALL,
        priority=GUARDRAIL_MESSAGE_ROUTE_PRIORITY,
    )
    async def guardrail_message_route(
        self, event: AstrMessageEvent, *_args, **_kwargs
    ) -> None:
        """Run route policy late in message handling, before AstrBot builds the LLM request."""
        if not self or not getattr(self, "normalized_config", None):
            return
        lease = self.adapter.get_event_extra(event, MESSAGE_STAGE_LOCK_EXTRA, None)
        owns_lease = False
        if lease is None or getattr(lease, "released", False):
            lease = await self.umo_locks.acquire(self.adapter.get_umo(event))
            owns_lease = True
        try:
            rail_context = await self._pipeline_for_event(event).run_message_route(event)
        except Exception as exc:
            logger.error("[LLMGuardrail] message route pipeline failed: %s", exc, exc_info=True)
            return
        finally:
            if owns_lease or lease is not None:
                releaser = getattr(lease, "release", None)
                if callable(releaser):
                    await releaser()
        self._log_context_summary("message_route", rail_context)

    @filter.on_llm_request()
    async def on_llm_request(
        self, event: AstrMessageEvent, req: ProviderRequest, *_args, **_kwargs
    ) -> None:
        """Run final request checks and prompt mutations before the main model call."""
        if not self or not getattr(self, "normalized_config", None):
            return
        if self._is_internal_request(req):
            return
        try:
            async with self.umo_locks.hold(self.adapter.get_umo(event)):
                rail_context = await self._pipeline_for_event(event).run_request(event, req)
        except Exception as exc:
            logger.error("[LLMGuardrail] request pipeline failed: %s", exc, exc_info=True)
            return
        self._log_context_summary("request", rail_context)

    @filter.on_llm_response()
    async def on_llm_response(
        self, event: AstrMessageEvent, resp: LLMResponse, *_args, **_kwargs
    ) -> None:
        """Run output rail before the model response is sent."""
        if not self or not getattr(self, "normalized_config", None):
            return
        try:
            async with self.umo_locks.hold(self.adapter.get_umo(event)):
                rail_context = await self._pipeline_for_event(event).run_response(event, resp)
        except Exception as exc:
            logger.error("[LLMGuardrail] response pipeline failed: %s", exc, exc_info=True)
            return
        self._log_context_summary("response", rail_context)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("guardrail")
    async def guardrail_status(self, event: AstrMessageEvent):
        """Show the current LLM Guardrail P0 status."""
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
            enabled_rules = sum(1 for rule in rail.rules if rule.enabled and rule.valid)
            rail_lines.append(
                f"- {rail_name}: enabled={rail.enabled}, rules={enabled_rules}/{len(rail.rules)}"
            )

        lines = [
            "LLM Guardrail P0",
            f"- version: {PLUGIN_VERSION}",
            f"- schema: {cfg.schema_version}",
            "- session scope: "
            f"group={cfg.session_control.get('group_chat_mode', 'all_run')}, "
            f"private={cfg.session_control.get('private_chat_mode', 'all_run')}",
            f"- current UMO: {current_umo or '(empty)'}",
            f"- current session action: {session_decision.action} ({session_decision.reason})",
            f"- warnings: {len(cfg.warnings)}",
            *rail_lines,
            "- capabilities: keywords, regex, logic gates, request checks, prompt mutations, first-hit routing, output blocking/sanitizing",
        ]
        if cfg.warnings:
            lines.append("- first warning: " + self._clip_text(cfg.warnings[0], 160))
        yield event.plain_result("\n".join(lines))

    async def terminate(self) -> None:
        """Clean up plugin resources."""
        logger.info("[LLMGuardrail] stopped")

    def _pipeline_for_event(self, event: AstrMessageEvent) -> GuardrailPipeline:
        """Build a pipeline from the snapshot fixed to this request event."""

        snapshot = self.snapshot_manager.bind_event(self.adapter, event)
        return GuardrailPipeline(snapshot.runtime_config, self.adapter)

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

    @staticmethod
    def _should_keep_message_stage_lock(rail_context) -> bool:
        decision = rail_context.session_scope_decision
        return (
            decision is not None
            and decision.action == "run"
            and not rail_context.input_blocked
        )

    def _log_context_summary(self, phase: str, rail_context) -> None:
        if not self.normalized_config.debug_settings["logging"]:
            return
        matched = [
            result.rule_id
            for result in rail_context.results.values()
            if result.executed and result.matched
        ]
        executed = [
            result.rule_id
            for result in rail_context.results.values()
            if result.executed
        ]
        errors = [
            result.rule_id
            for result in rail_context.results.values()
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
            "[LLMGuardrail] %s | umo=%s | session=%s | executed=%s | matched=%s | errors=%s | input_blocked=%s | output_blocked=%s | route=%s | mutations=%s | warnings=%s | last_warning=%s",
            phase,
            rail_context.umo,
            session_action,
            ",".join(executed[:10]) or "-",
            ",".join(matched[:10]) or "-",
            ",".join(errors[:10]) or "-",
            rail_context.input_blocked,
            rail_context.output_blocked,
            route_label or "-",
            ",".join(mutations[:10]) or "-",
            len(rail_context.warnings),
            self._clip_text(rail_context.warnings[-1], 180)
            if rail_context.warnings
            else "-",
        )
