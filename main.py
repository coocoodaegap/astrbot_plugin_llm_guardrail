"""AstrBot LLM Guardrail plugin skeleton.

This file intentionally keeps runtime behavior light. The first goal is to let
the plugin load and expose a reviewable configuration panel before the real
guardrail pipeline is implemented.
"""

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import LLMResponse, ProviderRequest
from astrbot.api.star import Context, Star, register


PLUGIN_NAME = "astrbot_plugin_llm_guardrail"
PLUGIN_VERSION = "0.1.0"
INTERNAL_MARKER = "__astrbot_plugin_llm_guardrail_internal__"


@register(
    name=PLUGIN_NAME,
    author="AstrBot Guardrail Contributors",
    desc="LLM Guardrail Orchestrator: dynamic prompt injection, output checks, anti-injection, and model routing.",
    version=PLUGIN_VERSION,
    repo="https://github.com/coocoodaegap/astrbot_plugin_llm_guardrail",
)
class LlmGuardrailPlugin(Star):
    """LLM guardrail orchestrator placeholder."""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

    async def initialize(self) -> None:
        """Initialize the plugin."""
        logger.info(
            "[LLMGuardrail] loaded skeleton v%s | enabled=%s | mode=%s",
            PLUGIN_VERSION,
            self.config.get("enabled", True),
            self.config.get("runtime", {}).get("mode", "assist"),
        )

    @filter.on_llm_request()
    async def on_llm_request(
        self, event: AstrMessageEvent, req: ProviderRequest
    ) -> None:
        """LLM request hook placeholder.

        Real input checks, prompt patches, and model routing will be added after
        the configuration contract is reviewed.
        """
        if not self.config.get("enabled", True):
            return
        if self._is_internal_request(req):
            return
        if self.config.get("runtime", {}).get("debug", False):
            logger.info(
                "[LLMGuardrail] request observed | umo=%s | text=%s",
                getattr(event, "unified_msg_origin", ""),
                self._clip_text(getattr(event, "message_str", "")),
            )

    @filter.on_llm_response()
    async def on_llm_response(
        self, event: AstrMessageEvent, resp: LLMResponse
    ) -> None:
        """LLM response hook placeholder."""
        if not self.config.get("enabled", True):
            return
        if getattr(resp, "is_chunk", False):
            return
        if self.config.get("runtime", {}).get("debug", False):
            logger.info(
                "[LLMGuardrail] response observed | umo=%s | text=%s",
                getattr(event, "unified_msg_origin", ""),
                self._clip_text(getattr(resp, "completion_text", "")),
            )

    @filter.command("guardrail")
    async def guardrail_status(self, event: AstrMessageEvent):
        """Show the current LLM Guardrail skeleton status."""
        runtime = self.config.get("runtime", {}) or {}
        input_checks = self.config.get("input_checks", {}) or {}
        output_checks = self.config.get("output_checks", {}) or {}
        router = self.config.get("router", {}) or {}
        profile_cfg = self.config.get("profile_overrides", {}) or {}
        profiles = profile_cfg.get("profiles", []) or []

        lines = [
            "LLM Guardrail skeleton",
            f"- version: {PLUGIN_VERSION}",
            f"- enabled: {self.config.get('enabled', True)}",
            f"- mode: {runtime.get('mode', 'assist')}",
            f"- input checks: {input_checks.get('enabled', True)}",
            f"- output checks: {output_checks.get('enabled', True)}",
            f"- router: {router.get('enabled', False)}",
            f"- profiles: {len(profiles)}",
            "- note: runtime enforcement is not implemented yet",
        ]
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
