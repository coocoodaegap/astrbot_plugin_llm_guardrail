import asyncio
import importlib
import sys
import types
import unittest


def _install_astrbot_stubs():
    astrbot = types.ModuleType("astrbot")
    api = types.ModuleType("astrbot.api")
    api.AstrBotConfig = dict
    api.logger = types.SimpleNamespace(info=lambda *a, **k: None, error=lambda *a, **k: None)

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
        on_waiting_llm_request=passthrough_decorator,
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


class MainHandlerSignatureTests(unittest.TestCase):
    def test_message_handlers_accept_astrbot_extra_args(self):
        _install_astrbot_stubs()
        module = importlib.import_module("main")
        plugin = module.LlmGuardrailPlugin(object(), {"enabled": False})

        asyncio.run(
            plugin.guardrail_access_gate(object(), object(), object(), object())
        )
        asyncio.run(
            plugin.guardrail_waiting_rails(object(), object(), object(), object())
        )
        asyncio.run(
            plugin.on_llm_request(object(), object(), object())
        )
        asyncio.run(
            plugin.on_llm_response(object(), object(), object())
        )

    def test_message_handlers_skip_none_self_from_astrbot_edge_event(self):
        _install_astrbot_stubs()
        module = importlib.import_module("main")

        asyncio.run(
            module.LlmGuardrailPlugin.guardrail_access_gate(
                None, object(), object(), object(), object()
            )
        )
        asyncio.run(
            module.LlmGuardrailPlugin.guardrail_waiting_rails(
                None, object(), object(), object(), object()
            )
        )
        asyncio.run(
            module.LlmGuardrailPlugin.on_llm_request(
                None, object(), object(), object()
            )
        )
        asyncio.run(
            module.LlmGuardrailPlugin.on_llm_response(
                None, object(), object(), object()
            )
        )


if __name__ == "__main__":
    unittest.main()
