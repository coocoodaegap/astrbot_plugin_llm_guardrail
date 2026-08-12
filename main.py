"""AstrBot LLM Guardrail plugin."""

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import LLMResponse, ProviderRequest
from astrbot.api.star import Context, Star, register

try:
    from .adapters import AstrBotAdapter
    from .config import normalize_config
    from .rails import GuardrailPipeline
except ImportError:  # pragma: no cover - fallback for direct script loading
    from adapters import AstrBotAdapter
    from config import normalize_config
    from rails import GuardrailPipeline


PLUGIN_NAME = "astrbot_plugin_llm_guardrail"
PLUGIN_VERSION = "0.1.0"
INTERNAL_MARKER = "__astrbot_plugin_llm_guardrail_internal__"


@register(
    name=PLUGIN_NAME,
    author="Coocoodaegap",
    desc="LLM Guardrail Orchestrator: dynamic prompt injection, output checks, anti-injection, and model routing.",
    version=PLUGIN_VERSION,
    repo="https://github.com/coocoodaegap/astrbot_plugin_llm_guardrail",
)
class LlmGuardrailPlugin(Star):
    """LLM guardrail orchestrator."""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.normalized_config = normalize_config(config)
        self.adapter = AstrBotAdapter()
        self.pipeline = GuardrailPipeline(self.normalized_config, self.adapter)

    async def initialize(self) -> None:
        """Initialize the plugin."""
        self.normalized_config = normalize_config(self.config)
        self.pipeline = GuardrailPipeline(self.normalized_config, self.adapter)
        logger.info(
            "[LLMGuardrail] loaded P0 v%s | enabled=%s | warnings=%s",
            PLUGIN_VERSION,
            self.normalized_config.enabled,
            len(self.normalized_config.warnings),
        )

    @filter.on_llm_request()
    async def on_llm_request(
        self, event: AstrMessageEvent, req: ProviderRequest
    ) -> None:
        """Run input, prompt, and routing rails before the main model call."""
        if not self.normalized_config.enabled:
            return
        if self._is_internal_request(req):
            return
        try:
            rail_context = self.pipeline.run_request(event, req)
        except Exception as exc:
            logger.error("[LLMGuardrail] request pipeline failed: %s", exc, exc_info=True)
            return
        self._log_context_summary("request", rail_context)

    @filter.on_llm_response()
    async def on_llm_response(
        self, event: AstrMessageEvent, resp: LLMResponse
    ) -> None:
        """Run output rail before the model response is sent."""
        if not self.normalized_config.enabled:
            return
        try:
            rail_context = self.pipeline.run_response(event, resp)
        except Exception as exc:
            logger.error("[LLMGuardrail] response pipeline failed: %s", exc, exc_info=True)
            return
        self._log_context_summary("response", rail_context)

    @filter.command("guardrail")
    async def guardrail_status(self, event: AstrMessageEvent):
        """Show the current LLM Guardrail P0 status."""
        cfg = self.normalized_config
        current_umo = self.adapter.get_umo(event)
        current_session_active = self._session_active_for_umo(current_umo)
        group_only = cfg.global_default_settings.get("group_only", False)
        private_skipped = group_only and self.adapter.is_private_chat(event)
        rail_lines = []
        for rail_name in ("input_rail", "prompt_rail", "routing_rail", "output_rail"):
            rail = cfg.rails[rail_name]
            enabled_rules = sum(1 for rule in rail.rules if rule.enabled and rule.valid)
            rail_lines.append(
                f"- {rail_name}: enabled={rail.enabled}, rules={enabled_rules}/{len(rail.rules)}"
            )

        lines = [
            "LLM Guardrail P0",
            f"- version: {PLUGIN_VERSION}",
            f"- schema: {cfg.schema_version}",
            f"- enabled: {cfg.enabled}",
            f"- session filter: {cfg.session_control.get('filter_type', 'blacklist')}",
            f"- current UMO: {current_umo or '(empty)'}",
            f"- current session active: {current_session_active and not private_skipped}",
            f"- group_only private skipped: {private_skipped}",
            f"- debug: {cfg.global_default_settings.get('debug', False)}",
            f"- warnings: {len(cfg.warnings)}",
            *rail_lines,
            "- capabilities: keywords, regex, logic gates, prompt mutations, first-hit routing, output blocking/sanitizing",
        ]
        if cfg.warnings:
            lines.append("- first warning: " + self._clip_text(cfg.warnings[0], 160))
        yield event.plain_result("\n".join(lines))

    async def terminate(self) -> None:
        """Clean up plugin resources."""
        logger.info("[LLMGuardrail] stopped")

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

    def _session_active_for_umo(self, umo: str) -> bool:
        session_control = self.normalized_config.session_control
        filter_type = session_control.get("filter_type", "blacklist")
        whitelist = set(session_control.get("whitelist", []))
        blacklist = set(session_control.get("blacklist", []))
        if filter_type == "whitelist":
            return bool(umo and umo in whitelist)
        return not (umo and umo in blacklist)

    def _log_context_summary(self, phase: str, rail_context) -> None:
        if not self.normalized_config.global_default_settings.get("debug", False):
            return
        matched = [
            result.rule_id
            for result in rail_context.results.values()
            if result.executed and result.matched
        ]
        logger.info(
            "[LLMGuardrail] %s | umo=%s | matched=%s | input_blocked=%s | output_blocked=%s | route=%s | warnings=%s",
            phase,
            rail_context.umo,
            ",".join(matched[:10]) or "-",
            rail_context.input_blocked,
            rail_context.output_blocked,
            rail_context.route_decision.provider_id
            if rail_context.route_decision
            else "-",
            len(rail_context.warnings),
        )
