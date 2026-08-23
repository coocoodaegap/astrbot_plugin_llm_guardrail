import asyncio
import importlib
import sys
import types
import unittest
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from core import NodeResult, NodeSignal, RailContext, RouteDecision


def _install_astrbot_stubs():
    astrbot = types.ModuleType("astrbot")
    api = types.ModuleType("astrbot.api")
    api.AstrBotConfig = dict
    api.logger = types.SimpleNamespace(
        info=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
    )
    event = types.ModuleType("astrbot.api.event")
    event.AstrMessageEvent = object

    def passthrough_decorator(*_args, **_kwargs):
        def decorate(func):
            return func

        return decorate

    event.filter = types.SimpleNamespace(
        EventMessageType=types.SimpleNamespace(ALL="ALL"),
        PermissionType=types.SimpleNamespace(ADMIN="ADMIN"),
        event_message_type=passthrough_decorator,
        on_llm_request=passthrough_decorator,
        on_llm_response=passthrough_decorator,
        permission_type=passthrough_decorator,
        command=passthrough_decorator,
    )
    provider = types.ModuleType("astrbot.api.provider")
    provider.LLMResponse = object
    provider.ProviderRequest = object
    star = types.ModuleType("astrbot.api.star")
    star.Context = object

    class Star:
        def __init__(self, context):
            self.context = context

    star.Star = Star
    star.register = passthrough_decorator
    sys.modules["astrbot"] = astrbot
    sys.modules["astrbot.api"] = api
    sys.modules["astrbot.api.event"] = event
    sys.modules["astrbot.api.provider"] = provider
    sys.modules["astrbot.api.star"] = star


class _Event:
    def __init__(self):
        self.unified_msg_origin = "qq:group:1"
        self._extras = {}

    def get_extra(self, key, default=None):
        return self._extras.get(key, default)

    def set_extra(self, key, value):
        self._extras[key] = value


class _DirectRequest:
    provider_id = "provider-b"
    model = "model-b"


class _Response:
    def __init__(self, *, is_chunk=False):
        self.is_chunk = is_chunk


class _Pipeline:
    """Small real-handler harness; state recording remains in ``main``."""

    def __init__(self, contexts):
        self.contexts = contexts

    async def run_message_input(self, _event):
        return self.contexts["message_input"]

    async def run_message_route(self, _event):
        return self.contexts["message_route"]

    async def run_request(self, _event, _request):
        return self.contexts["request"]

    async def run_response(self, _event, response):
        return self.contexts["stream_chunk" if response.is_chunk else "response"]


class SessionPolicyRuntimeTests(unittest.TestCase):
    def test_runtime_observer_persists_block_signal_and_route_candidate(self):
        _install_astrbot_stubs()
        module = importlib.import_module("main")
        plugin = module.LlmGuardrailPlugin(object(), {})
        self.assertTrue(plugin.normalized_config.session_policy_state["enabled"])
        event = _Event()
        plugin._ensure_policy_run(event)
        result = NodeResult(
            rail="input_rail",
            template_key="plain_keywords",
            node_id="risk",
            user_node_id="risk",
            anonymous=False,
            enabled=True,
            executed=True,
            matched=True,
            signal=NodeSignal(value=True, truthy=True, payload={"hit": "secret"}),
        )
        input_context = RailContext(
            event=event,
            request=None,
            response=None,
            umo=event.unified_msg_origin,
            original_input="secret",
            current_input="secret",
            current_output="",
            results={"risk": result},
            input_blocked=True,
            terminal_action={
                "rail": "input_rail",
                "source_kind": "rule",
                "node_id": "risk",
                "action": "block",
                "target": "input",
                "adapter_success": True,
            },
        )
        asyncio.run(
            plugin._record_session_policy_state(
                "message_input",
                event,
                input_context,
            )
        )
        blocked_detail = asyncio.run(
            plugin.session_policy_state.get_detail(
                event.unified_msg_origin,
                settings=plugin.normalized_config.session_policy_state,
            )
        )
        route_result = NodeResult(
            rail="routing_rail",
            template_key="route_policy",
            node_id="route-main",
            user_node_id="route-main",
            anonymous=False,
            enabled=True,
            executed=True,
            matched=True,
            signal=NodeSignal(value=True, truthy=True, payload={}),
            metadata={"provider_id": "provider-a", "applied": True},
        )
        event.set_extra("selected_provider", "provider-a")
        route_context = RailContext(
            event=event,
            request=None,
            response=None,
            umo=event.unified_msg_origin,
            original_input="secret",
            current_input="secret",
            current_output="",
            results={"route-main": route_result},
            route_decision=RouteDecision(
                provider_id="provider-a",
                source_node_id="route-main",
                applied=True,
            ),
        )
        asyncio.run(
            plugin._record_session_policy_state(
                "message_route",
                event,
                route_context,
            )
        )
        detail = asyncio.run(
            plugin.session_policy_state.get_detail(
                event.unified_msg_origin,
                settings=plugin.normalized_config.session_policy_state,
            )
        )

        self.assertTrue(blocked_detail.found)
        self.assertEqual(blocked_detail.record["last_policy_result"]["outcome"], "blocked")
        self.assertEqual(blocked_detail.record["last_policy_result"]["signals"][0]["signal"]["payload"], {"hit": "secret"})
        self.assertEqual(detail.record["route_candidate"]["provider_id"], "provider-a")
        self.assertEqual(detail.record["route_candidate"]["mode"], "observe_only")

    def test_request_target_observation_only_reads_direct_provider_request_fields(self):
        _install_astrbot_stubs()
        module = importlib.import_module("main")
        context = types.SimpleNamespace(
            get_current_chat_provider_id=lambda _umo: "session-default-provider"
        )
        plugin = module.LlmGuardrailPlugin(context, {"session_policy_state": {"enabled": True}})
        event = _Event()
        event.set_extra("selected_provider", "policy-selected-provider")
        direct = asyncio.run(plugin._request_target_observation(event, _DirectRequest()))
        unavailable = asyncio.run(plugin._request_target_observation(event, object()))

        self.assertEqual(direct, {
            "provider_id": "provider-b",
            "model_id": "model-b",
            "source": "provider_request",
        })
        self.assertEqual(unavailable, {
            "provider_id": "",
            "model_id": "",
            "source": "unavailable",
        })

    def test_real_handlers_share_run_and_ignore_stream_chunk_monitor_writes(self):
        _install_astrbot_stubs()
        module = importlib.import_module("main")
        plugin = module.LlmGuardrailPlugin(
            object(),
            {"session_policy_state": {"enabled": True}},
        )
        event = _Event()
        request = _DirectRequest()
        event.set_extra("selected_provider", "provider-a")
        input_result = NodeResult(
            rail="input_rail",
            template_key="plain_keywords",
            node_id="risk",
            user_node_id="risk",
            anonymous=False,
            enabled=True,
            executed=True,
            matched=True,
            signal=NodeSignal(value=True, truthy=True, payload={"hit": "secret"}),
        )
        route_result = NodeResult(
            rail="routing_rail",
            template_key="route_policy",
            node_id="route-main",
            user_node_id="route-main",
            anonymous=False,
            enabled=True,
            executed=True,
            matched=True,
            signal=NodeSignal(value=True, truthy=True, payload={}),
            metadata={"provider_id": "provider-a", "applied": True},
        )
        base_kwargs = {
            "event": event,
            "umo": event.unified_msg_origin,
            "original_input": "secret",
            "current_input": "secret",
            "current_output": "",
        }
        pipeline = _Pipeline(
            {
                "message_input": RailContext(
                    request=None,
                    response=None,
                    results={"risk": input_result},
                    **base_kwargs,
                ),
                "message_route": RailContext(
                    request=None,
                    response=None,
                    results={"route-main": route_result},
                    route_decision=RouteDecision(
                        provider_id="provider-a",
                        source_node_id="route-main",
                        applied=True,
                    ),
                    **base_kwargs,
                ),
                "request": RailContext(
                    request=request,
                    response=None,
                    results={"risk": input_result},
                    **base_kwargs,
                ),
                "response": RailContext(
                    request=None,
                    response=_Response(),
                    results={"risk": input_result},
                    **base_kwargs,
                ),
                "stream_chunk": RailContext(
                    request=None,
                    response=_Response(is_chunk=True),
                    results={},
                    **base_kwargs,
                ),
            }
        )
        plugin._pipeline_for_event = lambda _event: pipeline

        async def run_case():
            await plugin.guardrail_message_input(event)
            await plugin.guardrail_message_route(event)
            await plugin.on_llm_request(event, request)
            await plugin.on_llm_response(event, _Response())
            before_chunk = await plugin.session_policy_state.get_detail(
                event.unified_msg_origin,
                settings=plugin.normalized_config.session_policy_state,
            )
            await plugin.on_llm_response(event, _Response(is_chunk=True))
            after_chunk = await plugin.session_policy_state.get_detail(
                event.unified_msg_origin,
                settings=plugin.normalized_config.session_policy_state,
            )
            return before_chunk, after_chunk

        before_chunk, after_chunk = asyncio.run(run_case())

        self.assertTrue(before_chunk.found)
        result = before_chunk.record["last_policy_result"]
        self.assertEqual(result["last_stage"], "response")
        self.assertEqual(result["run_id"], event.get_extra(module.POLICY_RUN_ID_EXTRA))
        self.assertEqual(
            result["started_at"],
            event.get_extra(module.POLICY_RUN_STARTED_AT_EXTRA),
        )
        self.assertEqual(before_chunk.record["route_candidate"]["provider_id"], "provider-a")
        self.assertEqual(
            before_chunk.record["last_request_target_observation"],
            {
                "observation_revision": 1,
                "run_id": result["run_id"],
                "provider_id": "provider-b",
                "model_id": "model-b",
                "source": "provider_request",
                "observed_at": before_chunk.record["last_request_target_observation"]["observed_at"],
            },
        )
        self.assertEqual(
            before_chunk.record["record_revision"],
            after_chunk.record["record_revision"],
        )
        self.assertEqual(
            before_chunk.record["activities"],
            after_chunk.record["activities"],
        )

    def test_monitor_failure_does_not_break_request_handler(self):
        _install_astrbot_stubs()
        module = importlib.import_module("main")
        plugin = module.LlmGuardrailPlugin(
            object(),
            {"session_policy_state": {"enabled": True}},
        )
        event = _Event()
        request = _DirectRequest()
        rail_context = RailContext(
            event=event,
            request=request,
            response=None,
            umo=event.unified_msg_origin,
            original_input="",
            current_input="",
            current_output="",
        )

        class _RequestPipeline:
            called = False

            async def run_request(self, _event, _request):
                self.called = True
                return rail_context

        class _BrokenMonitor:
            async def record_phase(self, *_args, **_kwargs):
                raise RuntimeError("storage unavailable")

        pipeline = _RequestPipeline()
        plugin._pipeline_for_event = lambda _event: pipeline
        plugin.session_policy_state = _BrokenMonitor()

        asyncio.run(plugin.on_llm_request(event, request))

        self.assertTrue(pipeline.called)


if __name__ == "__main__":
    unittest.main()
