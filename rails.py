"""P0 rail orchestration."""

from __future__ import annotations

from typing import Any

try:
    from .actions import ActionPlan, resolve_action_plan
    from .adapters import AstrBotAdapter
    from .config import (
        NormalizedConfig,
        NormalizedRail,
        NormalizedRule,
        resolve_session_scope,
    )
    from .core import (
        RailContext,
        RouteDecision,
        RuleResult,
        RuleScheduler,
        build_graph_index,
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
    from actions import ActionPlan, resolve_action_plan
    from adapters import AstrBotAdapter
    from config import (
        NormalizedConfig,
        NormalizedRail,
        NormalizedRule,
        resolve_session_scope,
    )
    from core import (
        RailContext,
        RouteDecision,
        RuleResult,
        RuleScheduler,
        build_graph_index,
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
STATE_EXTRA_KEY = "_llm_guardrail_state"

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
        self.graph = build_graph_index(config)
        self.scheduler = RuleScheduler(self.graph)

    async def run_message(self, event: Any) -> RailContext:
        context = await self.run_message_input(event)
        if context.input_blocked:
            return context
        return await self.run_message_route(event)

    async def run_message_input(self, event: Any) -> RailContext:
        context = self._make_request_context(event, request=None)
        if not self.adapter.is_llm_candidate_event(event):
            self._store_context(event, context)
            return context
        if not self._admit_session(event, context):
            self._store_context(event, context)
            return context

        input_rail = self.config.rails["input_rail"]
        if input_rail.enabled:
            await self._run_input_rail(input_rail, context)

        self._store_context(event, context)
        return context

    async def run_message_route(self, event: Any) -> RailContext:
        context = self._make_request_context(event, request=None)
        if not self.adapter.is_llm_candidate_event(event):
            self._store_context(event, context)
            return context
        if not self._admit_session(event, context):
            self._store_context(event, context)
            return context
        if context.input_blocked:
            self._store_context(event, context)
            return context

        routing_rail = self.config.rails["routing_rail"]
        if routing_rail.enabled:
            await self._run_routing_rail(routing_rail, context)

        self._store_context(event, context)
        return context

    async def run_request(self, event: Any, request: Any) -> RailContext:
        context = self._make_request_context(event, request)
        if self._bypass_admin_command(event):
            self._store_context(event, context)
            return context
        if not self._admit_session(event, context):
            self._store_context(event, context)
            return context

        request_rail = self.config.rails["request_rail"]
        if request_rail.enabled:
            await self._run_request_rail(request_rail, context)

        if context.input_blocked:
            self._store_context(event, context)
            return context

        prompt_rail = self.config.rails["prompt_rail"]
        if prompt_rail.enabled:
            await self._run_prompt_rail(prompt_rail, context)

        self._store_context(event, context)
        return context

    async def run_response(self, event: Any, response: Any) -> RailContext:
        context = self._make_response_context(event, response)
        if getattr(response, "is_chunk", False):
            self._store_context(event, context)
            return context
        if self._bypass_admin_command(event):
            self._store_context(event, context)
            return context
        if not self._admit_session(event, context):
            self._store_context(event, context)
            return context

        output_rail = self.config.rails["output_rail"]
        if output_rail.enabled:
            await self._run_output_rail(output_rail, context)

        self._store_context(event, context)
        return context

    def _make_request_context(self, event: Any, request: Any) -> RailContext:
        previous_results = self.adapter.get_event_extra(event, RESULTS_EXTRA_KEY, {})
        if not isinstance(previous_results, dict):
            previous_results = {}
        previous_warnings = self.adapter.get_event_extra(event, WARNINGS_EXTRA_KEY, [])
        if not isinstance(previous_warnings, list):
            previous_warnings = []
        previous_state = self.adapter.get_event_extra(event, STATE_EXTRA_KEY, {})
        if not isinstance(previous_state, dict):
            previous_state = {}
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
            results=dict(previous_results),
            warnings=list(previous_warnings),
            input_blocked=bool(previous_state.get("input_blocked", False)),
            output_blocked=bool(previous_state.get("output_blocked", False)),
        )

    def _make_response_context(self, event: Any, response: Any) -> RailContext:
        previous_results = self.adapter.get_event_extra(event, RESULTS_EXTRA_KEY, {})
        if not isinstance(previous_results, dict):
            previous_results = {}
        previous_warnings = self.adapter.get_event_extra(event, WARNINGS_EXTRA_KEY, [])
        if not isinstance(previous_warnings, list):
            previous_warnings = []
        previous_state = self.adapter.get_event_extra(event, STATE_EXTRA_KEY, {})
        if not isinstance(previous_state, dict):
            previous_state = {}
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
            input_blocked=bool(previous_state.get("input_blocked", False)),
            output_blocked=bool(previous_state.get("output_blocked", False)),
        )
        return context

    def _admit_session(self, event: Any, context: RailContext) -> bool:
        if not self.config.enabled:
            return False
        decision = resolve_session_scope(
            self.config.session_control,
            context.umo,
            self.adapter.is_private_chat(event),
        )
        context.session_scope_decision = decision
        if decision.action == "run":
            return True
        if decision.action == "block":
            self._apply_session_control_block(context)
        return False

    def _bypass_admin_command(self, event: Any) -> bool:
        return self.adapter.is_admin(event) and self.adapter.is_command_event(event)

    def _apply_session_control_block(self, context: RailContext) -> None:
        context.input_blocked = True
        message = DEFAULT_INPUT_BLOCK_MESSAGE
        if context.response is not None:
            context.output_blocked = True
            if self.config.global_default_settings.get("reply_placeholder_on_block", True):
                adapter_result = self.adapter.set_response_text(context.response, message)
            else:
                adapter_result = self.adapter.stop_event(context.event)
        elif self.config.global_default_settings.get("reply_placeholder_on_block", True):
            adapter_result = self.adapter.set_block_result(context.event, message)
        else:
            adapter_result = self.adapter.stop_event(context.event)
        context.warnings.extend(adapter_result.warnings)

    def _store_context(self, event: Any, context: RailContext) -> None:
        result = self.adapter.set_event_extra(event, RESULTS_EXTRA_KEY, context.results)
        context.warnings.extend(result.warnings)
        result = self.adapter.set_event_extra(event, WARNINGS_EXTRA_KEY, context.warnings)
        context.warnings.extend(result.warnings)
        state = {
            "input_blocked": context.input_blocked,
            "output_blocked": context.output_blocked,
        }
        result = self.adapter.set_event_extra(event, STATE_EXTRA_KEY, state)
        context.warnings.extend(result.warnings)

    async def _run_input_rail(self, rail: NormalizedRail, context: RailContext) -> None:
        check_original_only = bool(rail.settings.get("check_original_only", True))
        max_chars = int(rail.settings.get("max_text_chars", 6000))
        current_text = clip_text(
            context.original_input
            if check_original_only
            else self.adapter.get_request_prompt(context.request) or context.current_input,
            max_chars,
        )

        async def execute(rule: NormalizedRule, ctx: RailContext) -> RuleResult:
            nonlocal current_text
            result = evaluate_text_rule(rule, ctx, current_text)
            plan = resolve_action_plan(rail, result)
            self._apply_input_action(rail, ctx, result, current_text, plan)
            if plan.mutate_text:
                current_text = ctx.current_input
            return result

        await self.scheduler.run_async(
            rail,
            context,
            execute,
            should_stop=lambda ctx: ctx.input_blocked,
        )

    async def _run_request_rail(self, rail: NormalizedRail, context: RailContext) -> None:
        max_chars = int(rail.settings.get("max_text_chars", 6000))
        current_text = clip_text(
            self.adapter.get_request_prompt(context.request) or context.current_input,
            max_chars,
        )

        async def execute(rule: NormalizedRule, ctx: RailContext) -> RuleResult:
            nonlocal current_text
            result = evaluate_text_rule(rule, ctx, current_text)
            plan = resolve_action_plan(rail, result)
            self._apply_input_action(rail, ctx, result, current_text, plan)
            if plan.mutate_text:
                current_text = self.adapter.get_request_prompt(ctx.request) or ctx.current_input
            return result

        await self.scheduler.run_async(
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
        plan: ActionPlan,
    ) -> None:
        if plan.action in {"none", "observe"}:
            return
        if plan.mutate_text:
            rule = self._rule_by_id(rail, result.rule_id)
            replacement = str(rule.config.get("sanitizer", ""))
            sanitized = apply_span_replacements(
                inspected_text, result.hits, replacement
            )
            context.current_input = sanitized
            if context.request is None:
                adapter_result = self.adapter.set_event_text(context.event, sanitized)
            else:
                prompt = self.adapter.get_request_prompt(context.request)
                if prompt == inspected_text:
                    new_prompt = sanitized
                else:
                    new_prompt = apply_literal_replacements(
                        prompt, result.hits, replacement
                    )
                adapter_result = self.adapter.set_request_prompt(context.request, new_prompt)
            context.warnings.extend(adapter_result.warnings)
            return
        if plan.block:
            context.input_blocked = True
            message = str(rail.settings.get("block_message", "")).strip()
            if not message:
                message = DEFAULT_INPUT_BLOCK_MESSAGE
            if self.config.global_default_settings.get("reply_placeholder_on_block", True):
                adapter_result = self.adapter.set_block_result(context.event, message)
            else:
                adapter_result = self.adapter.stop_event(context.event)
            context.warnings.extend(adapter_result.warnings)

    async def _run_prompt_rail(self, rail: NormalizedRail, context: RailContext) -> None:
        async def execute(rule: NormalizedRule, ctx: RailContext) -> RuleResult:
            if rule.template_key == "logic_gate":
                return evaluate_logic_gate(rule, ctx)
            if rule.template_key == "replace_input":
                return self._execute_replace_input(rule, ctx)
            if rule.template_key == "strengthen_prompt":
                return self._execute_strengthen_prompt(rule, ctx)
            return skipped_result(rule, "unsupported_template")

        await self.scheduler.run_async(rail, context, execute)

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

    async def _run_routing_rail(self, rail: NormalizedRail, context: RailContext) -> None:
        async def execute(rule: NormalizedRule, ctx: RailContext) -> RuleResult:
            if rule.template_key == "logic_gate":
                return evaluate_logic_gate(rule, ctx)
            if rule.template_key == "route_policy":
                return await self._execute_route_policy(rule, ctx)
            return skipped_result(rule, "unsupported_template")

        await self.scheduler.run_async(
            rail,
            context,
            execute,
            should_stop=lambda ctx: (
                ctx.route_decision is not None and ctx.route_decision.applied
            ),
        )

    async def _execute_route_policy(
        self, rule: NormalizedRule, context: RailContext
    ) -> RuleResult:
        if context.route_decision is not None:
            return skipped_result(rule, "route_already_selected")
        provider_id = str(rule.config.get("provider_id", "")).strip()
        adapter_success = True
        adapter_warnings: list[str] = []
        adapter_metadata: dict[str, Any] = {}
        if provider_id:
            adapter_result = await self.adapter.apply_route(
                context.event, context.request, provider_id
            )
            adapter_success = adapter_result.success
            adapter_warnings = list(adapter_result.warnings)
            adapter_metadata = dict(adapter_result.metadata)
            context.warnings.extend(adapter_warnings)
        context.route_decision = RouteDecision(
            provider_id=provider_id,
            source_rule_id=rule.rule_id,
            applied=adapter_success,
            reason="" if adapter_success else "; ".join(adapter_warnings),
        )
        return make_result(
            rule,
            matched=adapter_success,
            metadata={
                "provider_id": provider_id,
                "applied": adapter_success,
                "default_route": (not bool(provider_id))
                or bool(adapter_metadata.get("default_route")),
                **adapter_metadata,
            },
        )

    async def _run_output_rail(self, rail: NormalizedRail, context: RailContext) -> None:
        max_chars = int(rail.settings.get("max_text_chars", 6000))
        current_text = clip_text(context.current_output, max_chars)

        async def execute(rule: NormalizedRule, ctx: RailContext) -> RuleResult:
            nonlocal current_text
            result = evaluate_text_rule(rule, ctx, current_text)
            plan = resolve_action_plan(rail, result)
            self._apply_output_action(rail, ctx, result, current_text, plan)
            if plan.mutate_text:
                current_text = ctx.current_output
            return result

        await self.scheduler.run_async(
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
        plan: ActionPlan,
    ) -> None:
        if plan.action in {"none", "observe"}:
            return
        if plan.mutate_text:
            rule = self._rule_by_id(rail, result.rule_id)
            replacement = str(rule.config.get("sanitizer", ""))
            sanitized = apply_span_replacements(
                inspected_text, result.hits, replacement
            )
            context.current_output = sanitized
            adapter_result = self.adapter.set_response_text(context.response, sanitized)
            context.warnings.extend(adapter_result.warnings)
            return
        if plan.block:
            context.output_blocked = True
            message = str(rail.settings.get("block_message", "")).strip()
            if not message:
                message = DEFAULT_OUTPUT_BLOCK_MESSAGE
            if self.config.global_default_settings.get("reply_placeholder_on_block", True):
                adapter_result = self.adapter.set_response_text(context.response, message)
            else:
                adapter_result = self.adapter.stop_event(context.event)
            context.warnings.extend(adapter_result.warnings)

    @staticmethod
    def _rule_by_id(rail: NormalizedRail, rule_id: str) -> NormalizedRule:
        for rule in rail.rules:
            if rule.rule_id == rule_id:
                return rule
        raise KeyError(rule_id)
