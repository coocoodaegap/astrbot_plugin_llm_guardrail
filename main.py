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
    from .access_control import AccessControlService
    from .adapters import AstrBotAdapter, ROUTE_SELECTED_PROVIDER_EXTRA
    from .config import resolve_session_scope
    from .constants import (
        GUARDRAIL_MESSAGE_INPUT_PRIORITY,
        GUARDRAIL_MESSAGE_ROUTE_PRIORITY,
        INTERNAL_MARKER,
    )
    from .rails import GuardrailPipeline
    from .pages_api import GuardrailPagesApiMixin
    from .rag_experience import RagExperienceService
    from .session_policy_state import SessionPolicyStateService
    from .session_lock import UmoLockManager, get_global_umo_lock_manager
    from .snapshots import ConfigSnapshotManager
    from .state import AstrBotKvStateStore, MemoryStateStore, StateStore
except ImportError:  # pragma: no cover - fallback for direct script loading
    from access_control import AccessControlService
    from adapters import AstrBotAdapter, ROUTE_SELECTED_PROVIDER_EXTRA
    from config import resolve_session_scope
    from constants import (
        GUARDRAIL_MESSAGE_INPUT_PRIORITY,
        GUARDRAIL_MESSAGE_ROUTE_PRIORITY,
        INTERNAL_MARKER,
    )
    from rails import GuardrailPipeline
    from pages_api import GuardrailPagesApiMixin
    from rag_experience import RagExperienceService
    from session_policy_state import SessionPolicyStateService
    from session_lock import UmoLockManager, get_global_umo_lock_manager
    from snapshots import ConfigSnapshotManager
    from state import AstrBotKvStateStore, MemoryStateStore, StateStore


PLUGIN_NAME = "astrbot_plugin_llm_guardrail"
PLUGIN_VERSION = "0.2.0"
MESSAGE_STAGE_LOCK_EXTRA = "_llm_guardrail_message_stage_lock"
POLICY_RUN_ID_EXTRA = "_llm_guardrail_policy_run_id"
POLICY_RUN_STARTED_AT_EXTRA = "_llm_guardrail_policy_run_started_at"

_PHASE_RAILS: dict[str, tuple[str, ...]] = {
    "message_input": ("input_rail",),
    "message_route": ("routing_rail",),
    "request": ("request_rail", "prompt_rail"),
    "response": ("output_rail",),
}


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
            "[LLMGuardrail] loaded P2 v%s | warnings=%s",
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
            await self._record_session_policy_state(
                "message_input",
                event,
                rail_context,
            )
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
            await self._record_session_policy_state(
                "message_route",
                event,
                rail_context,
            )
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

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("guardrail")
    async def guardrail_status(self, event: AstrMessageEvent):
        """Show the current LLM Guardrail P2 status."""
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
            "LLM Guardrail P2",
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
        ``provider_id`` and ``model`` attributes.  When they do not, the
        monitor records an unavailable observation instead of substituting the
        UMO's session-default Provider, which is not request-scoped evidence.
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
