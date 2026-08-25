import asyncio
import importlib
import sys
import types
import unittest


class _CommandEvent:
    def __init__(self, *, platform_name="aiocqhttp", sender_id="admin"):
        self.platform_name = platform_name
        self.sender_id = sender_id

    def get_platform_name(self):
        return self.platform_name

    def get_sender_id(self):
        return self.sender_id

    def plain_result(self, text):
        return {"plain": text}


async def _collect_results(generator):
    return [result async for result in generator]


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

    def command_group_decorator(*_args, **_kwargs):
        def decorate(func):
            func.command = passthrough_decorator
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
        command_group=command_group_decorator,
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

    def test_access_control_commands_use_current_adapter_and_manual_command_reason(self):
        _install_astrbot_stubs()
        module = importlib.import_module("main")
        plugin = module.LlmGuardrailPlugin(object(), {"enabled": False})
        event = _CommandEvent()

        async def run_case():
            overall_status = await _collect_results(plugin.guardrail_status(event))
            ban = await _collect_results(
                plugin.guardrail_access_ban(event, "123456", "15")
            )
            ban_record = await plugin.access_control.get_active_record(
                module.make_principal_identity("aiocqhttp", "123456")
            )
            status = await _collect_results(
                plugin.guardrail_access_status(event, "123456")
            )
            listing = await _collect_results(plugin.guardrail_access_list(event, "ban", "1"))
            pardon = await _collect_results(
                plugin.guardrail_access_pardon(event, "123456")
            )
            release = await _collect_results(
                plugin.guardrail_access_release(event, "123456")
            )
            missing = await _collect_results(
                plugin.guardrail_access_status(event, "123456")
            )
            return overall_status, ban, ban_record, status, listing, pardon, release, missing

        overall_status, ban, ban_record, status, listing, pardon, release, missing = asyncio.run(run_case())

        self.assertIn("LLM Guardrail", overall_status[0]["plain"])
        self.assertIn("已封禁", ban[0]["plain"])
        self.assertEqual(ban_record["decision_reason_code"], "manual_command")
        self.assertIn("指令操作", status[0]["plain"])
        self.assertIn("ai…tp/12…56", listing[0]["plain"])
        self.assertIn("已赦免", pardon[0]["plain"])
        self.assertIn("永久", pardon[0]["plain"])
        self.assertIn("已解除赦免", release[0]["plain"])
        self.assertIn("没有有效决定", missing[0]["plain"])

    def test_access_control_command_rejects_invalid_duration_and_limit(self):
        _install_astrbot_stubs()
        module = importlib.import_module("main")
        plugin = module.LlmGuardrailPlugin(object(), {"enabled": False})
        event = _CommandEvent()

        async def run_case():
            duration = await _collect_results(
                plugin.guardrail_access_ban(event, "123456", "0")
            )
            limit = await _collect_results(plugin.guardrail_access_list(event, "ban", "101"))
            return duration, limit

        duration, limit = asyncio.run(run_case())

        self.assertEqual(duration[0]["plain"], "minutes 必须为 -1 或正整数。")
        self.assertEqual(limit[0]["plain"], "limit 必须是 1 到 100 的整数。")


if __name__ == "__main__":
    unittest.main()
