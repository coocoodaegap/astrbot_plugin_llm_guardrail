"""P0 rail orchestration."""

from __future__ import annotations

from typing import Any

try:
    from .adapters import AstrBotAdapter
    from .config import NormalizedConfig, NormalizedRail, NormalizedRule
    from .core import (
        RailContext,
        RouteDecision,
        RuleResult,
        RuleScheduler,
        make_result,
        skipped_result,
    )
    from .rules import (
        apply_literal_replacements,
        apply_span_replacements,
        clip_text,
        evaluate_logic_gate,
        evaluate_text_rule,
    )
except ImportError:  # pragma: no cover - fallback for direct script loading
    from adapters import AstrBotAdapter
    from config import NormalizedConfig, NormalizedRail, NormalizedRule
    from core import (
        RailContext,
        RouteDecision,
        RuleResult,
        RuleScheduler,
        make_result,
        skipped_result,
    )
    from rules import (
        apply_literal_replacements,
        apply_span_replacements,
        clip_text,
        evaluate_logic_gate,
        evaluate_text_rule,
    )


RESULTS_EXTRA_KEY = "_llm_guardrail_results"
WARNINGS_EXTRA_KEY = "_llm_guardrail_warnings"

DEFAULT_INPUT_BLOCK_MESSAGE = "Request blocked by LLM Guardrail."
DEFAULT_OUTPUT_BLOCK_MESSAGE = "Response blocked by LLM Guardrail."


class GuardrailPipeline:
    def __init__(
        self,
        config: NormalizedConfig,
        adapter: AstrBotAdapter | None = None,
    ) -> None:
        self.config = config
        self.adapter = adapter or AstrBotAdapter()
        self.scheduler = RuleScheduler()

    def run_request(self, event: Any, request: Any) -> RailContext:
        context = self._make_request_context(event, request)
        if not self._in_scope(event, context):
            self._store_context(event, context)
            return context

        input_rail = self.config.rails["input_rail"]
        if input_rail.enabled:
            self._run_input_rail(input_rail, context)

        if not context.input_blocked:
            prompt_rail = self.config.rails["prompt_rail"]
            if prompt_rail.enabled:
                self._run_prompt_rail(prompt_rail, context)

        if not context.input_blocked:
            routing_rail = self.config.rails["routing_rail"]
            if routing_rail.enabled:
                self._run_routing_rail(routing_rail, context)

        self._store_context(event, context)
        return context

    def run_response(self, event: Any, response: Any) -> RailContext:
        context = self._make_response_context(event, response)
        if getattr(response, "is_chunk", False):
            self._store_context(event, context)
            return context
        if not self._in_scope(event, context):
            self._store_context(event, context)
            return context

        output_rail = self.config.rails["output_rail"]
        if output_rail.enabled:
            self._run_output_rail(output_rail, context)

        self._store_context(event, context)
        return context

    def _make_request_context(self, event: Any, request: Any) -> RailContext:
        original_input = self.adapter.get_event_text(event)
        prompt = self.adapter.get_request_prompt(request)
        return RailContext(
            event=event,
            request=request,
            response=None,
            umo=self.adapter.get_umo(event),
            original_input=original_input,
            current_input=prompt or original_input,
            current_output="",
        )

    def _make_response_context(self, event: Any, response: Any) -> RailContext:
        previous_results = self.adapter.get_event_extra(event, RESULTS_EXTRA_KEY, {})
        if not isinstance(previous_results, dict):
            previous_results = {}
        previous_warnings = self.adapter.get_event_extra(event, WARNINGS_EXTRA_KEY, [])
        if not isinstance(previous_warnings, list):
            previous_warnings = []
        context = RailContext(
            event=event,
            request=None,
            response=response,
            umo=self.adapter.get_umo(event),
            original_input=self.adapter.get_event_text(event),
            current_input=self.adapter.get_event_text(event),
            current_output=self.adapter.get_response_text(response),
            results=dict(previous_results),
            warnings=list(previous_warnings),
        )
        return context

    def _in_scope(self, event: Any, context: RailContext) -> bool:
        if not self.config.enabled:
            return False
        if self.config.global_default_settings.get("group_only", False):
            if self.adapter.is_private_chat(event):
                return False
        session_control = self.config.session_control
        umo = context.umo
        filter_type = session_control.get("filter_type", "blacklist")
        whitelist = set(session_control.get("whitelist", []))
        blacklist = set(session_control.get("blacklist", []))
        if filter_type == "whitelist":
            return bool(umo and umo in whitelist)
        return not (umo and umo in blacklist)

    def _store_context(self, event: Any, context: RailContext) -> None:
        result = self.adapter.set_event_extra(event, RESULTS_EXTRA_KEY, context.results)
        context.warnings.extend(result.warnings)
        result = self.adapter.set_event_extra(event, WARNINGS_EXTRA_KEY, context.warnings)
        context.warnings.extend(result.warnings)

    def _run_input_rail(self, rail: NormalizedRail, context: RailContext) -> None:
        check_original_only = bool(rail.settings.get("check_original_only", True))
        max_chars = int(rail.settings.get("max_text_chars", 6000))
        current_text = clip_text(
            context.original_input
            if check_original_only
            else self.adapter.get_request_prompt(context.request) or context.current_input,
            max_chars,
        )

        def execute(rule: NormalizedRule, ctx: RailContext) -> RuleResult:
            nonlocal current_text
            result = evaluate_text_rule(rule, ctx, current_text)
            self._apply_input_action(rail, ctx, result, current_text)
            if result.matched and self._resolve_input_action(rail, result) == "sanitize_input":
                current_text = ctx.current_input
            return result

        self.scheduler.run(
            rail,
            context,
            execute,
            should_stop=lambda ctx: ctx.input_blocked,
        )

    def _apply_input_action(
        self,
        rail: NormalizedRail,
        context: RailContext,
        result: RuleResult,
        inspected_text: str,
    ) -> None:
        if not result.matched:
            return
        action = self._resolve_input_action(rail, result)
        if action == "observe":
            return
        if action == "sanitize_input":
            replacement = str(
                self._rule_by_id(rail, result.rule_id).config.get("sanitizer", "")
            )
            sanitized = apply_span_replacements(
                inspected_text, result.hits, replacement
            )
            context.current_input = sanitized
            prompt = self.adapter.get_request_prompt(context.request)
            if prompt == inspected_text:
                new_prompt = sanitized
            else:
                new_prompt = apply_literal_replacements(prompt, result.hits, replacement)
            adapter_result = self.adapter.set_request_prompt(context.request, new_prompt)
            context.warnings.extend(adapter_result.warnings)
            return
        if action == "block_input":
            context.input_blocked = True
            message = str(rail.settings.get("block_message", "")).strip()
            if not message:
                message = DEFAULT_INPUT_BLOCK_MESSAGE
            if self.config.global_default_settings.get("reply_placeholder_on_block", True):
                adapter_result = self.adapter.set_block_result(context.event, message)
            else:
                adapter_result = self.adapter.stop_event(context.event)
            context.warnings.extend(adapter_result.warnings)

    def _run_prompt_rail(self, rail: NormalizedRail, context: RailContext) -> None:
        def execute(rule: NormalizedRule, ctx: RailContext) -> RuleResult:
            if rule.template_key == "logic_gate":
                return evaluate_logic_gate(rule, ctx)
            if rule.template_key == "replace_input":
                return self._execute_replace_input(rule, ctx)
            if rule.template_key == "strengthen_prompt":
                return self._execute_strengthen_prompt(rule, ctx)
            return skipped_result(rule, "unsupported_template")

        self.scheduler.run(rail, context, execute)

    def _execute_replace_input(
        self, rule: NormalizedRule, context: RailContext
    ) -> RuleResult:
        replacement = str(rule.config.get("replacement_text", ""))
        if replacement == "":
            context.warnings.append(f"{rule.rule_id}.replacement_text is empty")
        adapter_result = self.adapter.set_request_prompt(context.request, replacement)
        context.warnings.extend(adapter_result.warnings)
        if adapter_result.success:
            context.current_input = replacement
            context.prompt_mutations.append(
                {"rule_id": rule.rule_id, "kind": "replace_input"}
            )
        return make_result(
            rule,
            matched=adapter_result.success,
            metadata={"replacement_length": len(replacement)},
        )

    def _execute_strengthen_prompt(
        self, rule: NormalizedRule, context: RailContext
    ) -> RuleResult:
        insertion_text = str(rule.config.get("insertion_text", ""))
        if not insertion_text:
            context.warnings.append(f"{rule.rule_id}.insertion_text is empty")
            return make_result(rule, matched=False, metadata={"reason": "empty_text"})

        target = str(rule.config.get("insertion_target", "temp_user_context"))
        if target == "system_prefix":
            current = self.adapter.get_system_prompt(context.request)
            adapter_result = self.adapter.set_system_prompt(
                context.request, f"{insertion_text}\n\n{current}" if current else insertion_text
            )
        elif target == "system_suffix":
            current = self.adapter.get_system_prompt(context.request)
            adapter_result = self.adapter.set_system_prompt(
                context.request, f"{current}\n\n{insertion_text}" if current else insertion_text
            )
        elif target == "temp_user_context":
            adapter_result = self.adapter.append_temp_user_context(
                context.request, insertion_text
            )
        elif target == "input_wrapper":
            prompt = self.adapter.get_request_prompt(context.request)
            wrapped = (
                f"{insertion_text}\n\n"
                "<untrusted_user_input>\n"
                f"{prompt}\n"
                "</untrusted_user_input>"
            )
            adapter_result = self.adapter.set_request_prompt(context.request, wrapped)
            if adapter_result.success:
                context.current_input = wrapped
        else:
            adapter_result = self.adapter.append_temp_user_context(
                context.request, insertion_text
            )

        context.warnings.extend(adapter_result.warnings)
        if adapter_result.success:
            context.prompt_mutations.append(
                {
                    "rule_id": rule.rule_id,
                    "kind": "strengthen_prompt",
                    "target": target,
                    "text_length": len(insertion_text),
                }
            )
        return make_result(
            rule,
            matched=adapter_result.success,
            metadata={"target": target, "text_length": len(insertion_text)},
        )

    def _run_routing_rail(self, rail: NormalizedRail, context: RailContext) -> None:
        def execute(rule: NormalizedRule, ctx: RailContext) -> RuleResult:
            if rule.template_key == "logic_gate":
                return evaluate_logic_gate(rule, ctx)
            if rule.template_key == "route_policy":
                return self._execute_route_policy(rule, ctx)
            return skipped_result(rule, "unsupported_template")

        self.scheduler.run(rail, context, execute)

    def _execute_route_policy(
        self, rule: NormalizedRule, context: RailContext
    ) -> RuleResult:
        if context.route_decision is not None:
            return skipped_result(rule, "route_already_selected")
        provider_id = str(rule.config.get("provider_id", "")).strip()
        if not provider_id:
            provider_id = str(
                self.config.global_default_settings.get("default_llm_provider", "")
            ).strip()
        if not provider_id:
            context.warnings.append(f"{rule.rule_id}.provider_id is empty")
            return make_result(rule, matched=False, metadata={"reason": "empty_provider_id"})

        adapter_result = self.adapter.apply_route(context.event, context.request, provider_id)
        context.warnings.extend(adapter_result.warnings)
        context.route_decision = RouteDecision(
            provider_id=provider_id,
            source_rule_id=rule.rule_id,
            applied=adapter_result.success,
            reason="" if adapter_result.success else "; ".join(adapter_result.warnings),
        )
        return make_result(
            rule,
            matched=adapter_result.success,
            metadata={
                "provider_id": provider_id,
                "applied": adapter_result.success,
            },
        )

    def _run_output_rail(self, rail: NormalizedRail, context: RailContext) -> None:
        max_chars = int(rail.settings.get("max_text_chars", 6000))
        current_text = clip_text(context.current_output, max_chars)

        def execute(rule: NormalizedRule, ctx: RailContext) -> RuleResult:
            nonlocal current_text
            result = evaluate_text_rule(rule, ctx, current_text)
            self._apply_output_action(rail, ctx, result, current_text)
            if result.matched and self._resolve_output_action(rail, result) == "sanitize_output":
                current_text = ctx.current_output
            return result

        self.scheduler.run(
            rail,
            context,
            execute,
            should_stop=lambda ctx: ctx.output_blocked,
        )

    def _apply_output_action(
        self,
        rail: NormalizedRail,
        context: RailContext,
        result: RuleResult,
        inspected_text: str,
    ) -> None:
        if not result.matched:
            return
        action = self._resolve_output_action(rail, result)
        if action == "observe":
            return
        if action == "sanitize_output":
            replacement = str(
                self._rule_by_id(rail, result.rule_id).config.get("sanitizer", "")
            )
            sanitized = apply_span_replacements(
                inspected_text, result.hits, replacement
            )
            context.current_output = sanitized
            adapter_result = self.adapter.set_response_text(context.response, sanitized)
            context.warnings.extend(adapter_result.warnings)
            return
        if action == "block_output":
            context.output_blocked = True
            message = str(rail.settings.get("block_message", "")).strip()
            if not message:
                message = DEFAULT_OUTPUT_BLOCK_MESSAGE
            if self.config.global_default_settings.get("reply_placeholder_on_block", True):
                adapter_result = self.adapter.set_response_text(context.response, message)
            else:
                adapter_result = self.adapter.stop_event(context.event)
            context.warnings.extend(adapter_result.warnings)

    def _resolve_input_action(
        self, rail: NormalizedRail, result: RuleResult
    ) -> str:
        if result.action_on_hit == "default":
            return str(rail.settings.get("default_action_on_hit", "block_input"))
        return result.action_on_hit

    def _resolve_output_action(
        self, rail: NormalizedRail, result: RuleResult
    ) -> str:
        if result.action_on_hit == "default":
            return str(rail.settings.get("default_action_on_hit", "block_output"))
        return result.action_on_hit

    @staticmethod
    def _rule_by_id(rail: NormalizedRail, rule_id: str) -> NormalizedRule:
        for rule in rail.rules:
            if rule.rule_id == rule_id:
                return rule
        raise KeyError(rule_id)
