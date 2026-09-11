"""Exercise compiled policies at the pre-assembly boundary with a fake provider.

The runner models the SDK reset/step contract; this is not a live AstrBot test.
"""

import copy
import importlib
import types
import unittest
from enum import Enum
from unittest.mock import patch

from agent_entry import AgentRequestEntry
from internal_runtime import internal_guardrail_call, is_internal_guardrail_call
from policy_library import (
    PolicyComponent,
    PolicyDefinition,
    PolicyLibrary,
    PolicyRuleBinding,
    RuleDefinition,
)
from rails import (
    OUTPUT_HISTORY_DIRECTIVE_EXTRA_KEY,
    RESULTS_EXTRA_KEY,
    RETRY_REQUEST_SNAPSHOT_EXTRA_KEY,
)
from test_main_handlers import _install_astrbot_stubs
from test_pipeline import FakeContext, FakeEvent, FakeRequest, FakeResponse


class State(Enum):
    IDLE = 0
    DONE = 1


class RecordingProvider:
    provider_config = {"id": "explicit_agent_provider"}

    def __init__(self):
        self.calls = []

    async def text_chat(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        return FakeResponse("model answer")


class Runner:
    async def reset(self, provider, request, run_context, tool_executor, agent_hooks):
        self.provider = provider
        self.req = request
        self.run_context = run_context
        self.final_llm_resp = None
        self._state = State.IDLE
        run_context.messages = [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": request.prompt},
        ]
        for part in request.extra_user_content_parts:
            run_context.messages.append({"role": "user", "content": part.text})

    async def step(self):
        self.final_llm_resp = await self.provider.text_chat(
            contexts=self.run_context.messages, image_urls=self.req.image_urls,
            func_tool=getattr(self.req, "func_tool", None),
        )
        self._transition_state(State.DONE)
        yield self.final_llm_resp

    def _transition_state(self, state):
        self._state = state

    def get_final_llm_resp(self):
        return self.final_llm_resp


class AgentEntryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        _install_astrbot_stubs()
        self.module = importlib.import_module("main")
        self.context = FakeContext()
        self.plugin = self.module.LlmGuardrailPlugin(self.context, {
            "debug_settings": {"enable_agent_request_entry": True},
        })
        self.hooks = object()
        self.entry = AgentRequestEntry(self.context, self.hooks, self.plugin._prepare_agent_request)
        self.original_reset = Runner.reset
        self.entry.install(Runner)

    async def asyncTearDown(self):
        self.entry.uninstall()
        Runner.reset = self.original_reset

    async def policy(self, target="system_suffix", *, block=False, error=False):
        rules = [RuleDefinition("check", "plain_keywords", {"keywords": ["deny"]})]
        if error:
            rules = [RuleDefinition("check", "llm_review", {"audit_prompt": "review"})]
        rules.append(RuleDefinition("output_check", "plain_keywords", {"keywords": ["model"]}))
        components = [
            PolicyComponent("prepared", "compose_text", "request_rail", config={"template": "ADDED ${req_origin}"}),
            PolicyComponent("strengthen", "strengthen_prompt", "prompt_rail", config={
                "insertion_target": target, "insertion_text": "${prepared.value}",
            }),
            # These would visibly block or route if the bridge ran Step 1/2.
            PolicyComponent("input_stop", "random_signal", "input_rail", action_on_hit="block", config={"probability": 1.0}),
        ]
        library = PolicyLibrary(rules=tuple(rules), policies=(PolicyDefinition(
            "agent_policy", "Agent policy", bindings=(PolicyRuleBinding(
                "check", "request_rail", action_on_hit="block" if block else "observe",
                action_on_error="block" if error else "discard",
            ), PolicyRuleBinding("output_check", "output_rail", action_on_hit="observe")), components=tuple(components),
            node_order=("input_stop", "check", "prepared", "strengthen", "output_check"),
        ),), active_policy_id="agent_policy")
        result = await self.plugin.snapshot_manager.publish_policy_library(
            library, expected_revision=self.plugin.snapshot_manager.current.revision
        )
        self.assertTrue(result.success, result.diagnostics)

    async def run_request(self, req=None, event=None, *, context=None, hooks=None, runner=None):
        event = event or FakeEvent("event text differs from actual request")
        req = req or FakeRequest("actual request", "base")
        provider = RecordingProvider()
        runner = runner or Runner()
        run_context = types.SimpleNamespace(context=types.SimpleNamespace(
            context=context or self.context, event=event,
        ), messages=[])
        await runner.reset(provider, req, run_context, None, hooks or self.hooks)
        responses = [response async for response in runner.step()]
        return event, req, provider, runner, responses

    async def test_compiled_step3_payload_reaches_provider_in_all_four_targets(self):
        class TextPart:
            def __init__(self, text):
                self.text = text
            def mark_as_temp(self):
                self.temporary = True
                return self
        message_module = types.ModuleType("astrbot.core.agent.message")
        message_module.TextPart = TextPart
        with patch.dict("sys.modules", {"astrbot.core.agent.message": message_module}):
            for target in ("system_prefix", "system_suffix", "temp_user_context", "input_wrapper"):
                with self.subTest(target=target):
                    await self.policy(target)
                    request = FakeRequest("actual request", "base")
                    tools = request.func_tool = object()
                    media = request.image_urls = ["image://kept"]
                    history = request.contexts = [{"role": "assistant", "content": "previous"}]
                    event, req, provider, runner, _ = await self.run_request(request)
                    sent = provider.calls[0]["contexts"]
                    self.assertIn("ADDED actual request", str(sent))
                    self.assertNotIn("event text differs", str(sent))
                    self.assertIs(req.func_tool, tools)
                    self.assertIs(req.image_urls, media)
                    self.assertIs(req.contexts, history)
                    self.assertIs(runner.provider, provider)
                    results = event.get_extra(RESULTS_EXTRA_KEY)
                    self.assertNotIn("input_stop", results)
                    self.assertEqual(results["prepared"].signal.payload["value"], "ADDED actual request")
                    self.assertTrue(results["strengthen"].matched)
                    if target == "temp_user_context":
                        self.assertTrue(req.extra_user_content_parts[-1].temporary)

    async def test_normal_request_is_not_strengthened_twice_and_new_request_is_checked(self):
        await self.policy()
        event = FakeEvent()
        request = FakeRequest("one", "base")
        await self.plugin.on_llm_request(event, request)
        _, req, provider, _, _ = await self.run_request(request, event)
        self.assertEqual(req.system_prompt.count("ADDED"), 1)
        self.assertEqual(len(provider.calls), 1)
        _, req2, _, _, _ = await self.run_request(FakeRequest("two", "base"), event)
        self.assertIn("ADDED two", req2.system_prompt)

    async def test_block_never_calls_provider_and_gate_survives_uninstall(self):
        await self.policy(block=True)
        event, req, provider, runner, responses = await self.run_request(FakeRequest("deny"))
        self.assertEqual(provider.calls, [])
        self.assertEqual(responses, [])
        self.assertEqual(runner._state, State.DONE)
        self.assertIsNone(runner.get_final_llm_resp())
        self.assertEqual(req.system_prompt, "system")
        self.entry.uninstall()
        self.assertEqual([item async for item in runner.step()], [])
        self.assertEqual(provider.calls, [])
        self.entry.install(Runner)
        _, _, provider2, _, responses2 = await self.run_request(runner=runner)
        self.assertEqual(len(provider2.calls), 1)
        self.assertEqual(len(responses2), 1)

    async def test_error_action_block_has_no_provider_call(self):
        await self.policy(error=True)
        async def unavailable(*args, **kwargs):
            raise RuntimeError("review unavailable")
        with patch.object(self.plugin.adapter, "request_llm_text", unavailable):
            _, _, provider, _, _ = await self.run_request()
        self.assertEqual(provider.calls, [])

    async def test_other_context_and_custom_hooks_are_untouched(self):
        await self.policy()
        for kwargs in ({"context": object()}, {"hooks": object()}):
            event, req, provider, _, _ = await self.run_request(**kwargs)
            self.assertNotIn("ADDED", req.system_prompt)
            self.assertIsNone(event.get_extra(RESULTS_EXTRA_KEY))
            self.assertEqual(len(provider.calls), 1)

    async def test_legacy_internal_marker_is_checked_as_ordinary_input(self):
        await self.policy()
        legacy_marker = "__astrbot_plugin_llm_guardrail_internal__"

        event, req, provider, _, _ = await self.run_request(
            FakeRequest(legacy_marker)
        )

        self.assertIn(f"ADDED {legacy_marker}", req.system_prompt)
        self.assertIn("check", event.get_extra(RESULTS_EXTRA_KEY))
        self.assertEqual(len(provider.calls), 1)

    async def test_runtime_identity_skips_step1_step3_step5_and_agent_done(self):
        await self.policy()
        event = FakeEvent("deny")
        req = FakeRequest("deny", "base")
        history = types.SimpleNamespace(
            messages=[{"role": "assistant", "content": "original"}],
        )
        event.set_extra(
            OUTPUT_HISTORY_DIRECTIVE_EXTRA_KEY,
            {"action": "commit", "text": "replacement"},
        )

        with internal_guardrail_call():
            await self.plugin.guardrail_access_gate(event)
            await self.plugin.guardrail_waiting_rails(event)
            await self.plugin.on_llm_request(event, req)
            _, req, provider, _, responses = await self.run_request(req, event)
            await self.plugin.on_llm_response(event, responses[0])
            await self.plugin.on_agent_done(event, history, responses[0])

        self.assertEqual(req.system_prompt, "base")
        self.assertEqual(len(provider.calls), 1)
        self.assertIsNone(event.get_extra(RESULTS_EXTRA_KEY))
        self.assertEqual(history.messages[-1]["content"], "original")
        self.assertFalse(event.stopped)

    async def test_llm_review_nested_agent_call_uses_runtime_identity(self):
        await self.policy(error=True)
        nested = []

        async def nested_agent_review(chat_provider_id, prompt, system_prompt=None):
            self.assertTrue(is_internal_guardrail_call())
            event, req, provider, _, _ = await self.run_request(
                FakeRequest(prompt, system_prompt or ""),
                FakeEvent("nested review"),
            )
            nested.append((event, req, provider))
            return FakeResponse('{"matched": false, "payload": {}}')

        self.context.llm_generate = nested_agent_review
        _, _, outer_provider, _, responses = await self.run_request()

        self.assertEqual(len(nested), 1)
        nested_event, nested_req, nested_provider = nested[0]
        self.assertIsNone(nested_event.get_extra(RESULTS_EXTRA_KEY))
        self.assertNotIn("ADDED", nested_req.system_prompt)
        self.assertEqual(len(nested_provider.calls), 1)
        self.assertEqual(len(outer_provider.calls), 1)
        self.assertEqual(len(responses), 1)
        self.assertFalse(is_internal_guardrail_call())

    async def test_actual_provider_recorded_for_retry_and_output_hook_still_runs(self):
        await self.policy()
        event, _, provider, _, responses = await self.run_request()
        snapshot = event.get_extra(RETRY_REQUEST_SNAPSHOT_EXTRA_KEY)
        self.assertEqual(snapshot.provider_id, "explicit_agent_provider")
        self.assertEqual(snapshot.provider_source, "agent_runner")
        await self.plugin.on_llm_response(event, responses[0])
        self.assertTrue(event.get_extra(RESULTS_EXTRA_KEY)["output_check"].matched)
        observation = await self.plugin._request_target_observation(event, FakeRequest())
        self.assertEqual(observation["source"], "agent_runner")
        self.assertEqual(len(provider.calls), 1)

    async def test_rag_evidence_is_injected_into_actual_agent_request(self):
        library = PolicyLibrary(rules=(RuleDefinition(
            "rag", "rag_judge", {"knowledge_bases": ["policy"], "min_score": 0.7},
        ),), policies=(PolicyDefinition(
            "rag_agent", "RAG Agent", bindings=(PolicyRuleBinding(
                "rag", "request_rail", action_on_hit="observe",
            ),), components=(PolicyComponent(
                "strengthen", "strengthen_prompt", "prompt_rail", config={
                    "insertion_target": "system_suffix", "insertion_text": "${rag.matched_text}",
                },
            ),), node_order=("rag", "strengthen"),
        ),), active_policy_id="rag_agent")
        result = await self.plugin.snapshot_manager.publish_policy_library(library, expected_revision=0)
        self.assertTrue(result.success, result.diagnostics)
        self.context.kb_manager.retrieve_result = {"results": [
            {"text": "Use the relevant guidance.", "score": 0.9, "metadata": {}},
            {"text": "Below threshold.", "score": 0.1, "metadata": {}},
        ]}
        event, req, provider, _, _ = await self.run_request()
        self.assertIn("Use the relevant guidance.", req.system_prompt)
        self.assertNotIn("Below threshold.", req.system_prompt)
        self.assertIn("Use the relevant guidance.", str(provider.calls[0]["contexts"]))
        self.assertTrue(event.get_extra(RESULTS_EXTRA_KEY)["rag"].matched)

    async def test_scope_pass_and_disabled_entry_leave_provider_request_unchanged(self):
        await self.policy()
        snapshot = self.plugin.snapshot_manager.current
        settings = {name: copy.deepcopy(getattr(snapshot.runtime_config, name)) for name in (
            "fallback_policy_settings", "session_control", "access_control",
            "session_policy_state", "debug_settings",
        )}
        settings["session_control"]["group_chat_mode"] = "all_pass"
        result = await self.plugin.snapshot_manager.publish_system_settings(
            settings, snapshot.revision, persist_settings=lambda value: None,
        )
        self.assertTrue(result.success, result.diagnostics)
        _, req, provider, _, _ = await self.run_request()
        self.assertEqual(req.system_prompt, "base")
        self.assertEqual(len(provider.calls), 1)
        settings["session_control"]["group_chat_mode"] = "all_run"
        settings["debug_settings"]["enable_agent_request_entry"] = False
        result = await self.plugin.snapshot_manager.publish_system_settings(
            settings, result.snapshot.revision, persist_settings=lambda value: None,
        )
        self.assertTrue(result.success, result.diagnostics)
        event, req, provider, _, _ = await self.run_request()
        self.assertEqual(req.system_prompt, "base")
        self.assertIsNone(event.get_extra(RESULTS_EXTRA_KEY))
        self.assertEqual(len(provider.calls), 1)

    async def test_install_signature_validation_and_restore(self):
        self.entry.uninstall()
        self.assertIs(Runner.reset, self.original_reset)
        class Unsupported:
            async def reset(self, **kwargs):
                pass
        with self.assertRaisesRegex(RuntimeError, "signature"):
            self.entry.install(Unsupported)
        self.entry.install(Runner)
        second = AgentRequestEntry(self.context, self.hooks, self.plugin._prepare_agent_request)
        with self.assertRaisesRegex(RuntimeError, "already installed"):
            second.install(Runner)

    async def test_bridge_failure_preserves_request_and_default_is_off(self):
        await self.policy()
        self.assertFalse(self.module.LlmGuardrailPlugin(object(), {}).normalized_config.debug_settings["enable_agent_request_entry"])
        async def fail(event, request):
            request.prompt = "partial mutation"
            raise RuntimeError("bridge failure")
        failing_pipeline = types.SimpleNamespace(run_request=fail)
        with patch.object(self.plugin, "_pipeline_for_event", return_value=failing_pipeline):
            _, req, provider, _, _ = await self.run_request()
        self.assertEqual(req.prompt, "actual request")
        self.assertEqual(req.system_prompt, "base")
        self.assertEqual(provider.calls[0]["contexts"][-1]["content"], "actual request")

    async def test_uninstall_preserves_third_party_outer_wrapper(self):
        inner = Runner.reset
        async def outer(runner, *args, **kwargs):
            return await inner(runner, *args, **kwargs)
        Runner.reset = outer
        self.entry.uninstall()
        self.assertIs(Runner.reset, outer)
        await self.policy()
        _, req, provider, _, _ = await self.run_request()
        self.assertEqual(req.system_prompt, "base")
        self.assertEqual(len(provider.calls), 1)


if __name__ == "__main__":
    unittest.main()
