import asyncio
import types
import unittest

from adapters import AstrBotAdapter, RetryRequestSnapshot
from internal_runtime import internal_guardrail_call, is_internal_guardrail_call


class InternalRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_nested_scope_and_exception_restore_identity(self):
        self.assertFalse(is_internal_guardrail_call())

        with self.assertRaisesRegex(RuntimeError, "boom"):
            with internal_guardrail_call():
                self.assertTrue(is_internal_guardrail_call())
                with internal_guardrail_call():
                    self.assertTrue(is_internal_guardrail_call())
                self.assertTrue(is_internal_guardrail_call())
                raise RuntimeError("boom")

        self.assertFalse(is_internal_guardrail_call())

    async def test_concurrent_external_task_does_not_inherit_identity(self):
        entered = asyncio.Event()
        release = asyncio.Event()

        async def internal_worker():
            with internal_guardrail_call():
                entered.set()
                await release.wait()
                return is_internal_guardrail_call()

        async def external_worker():
            await entered.wait()
            observed = is_internal_guardrail_call()
            release.set()
            return observed

        internal, external = await asyncio.gather(
            internal_worker(), external_worker(),
        )

        self.assertTrue(internal)
        self.assertFalse(external)
        self.assertFalse(is_internal_guardrail_call())

    async def test_adapter_establishes_identity_and_restores_after_failure(self):
        observations = []

        class Context:
            providers = {"review": object()}

            async def get_current_chat_provider_id(self, _umo):
                return "review"

            def get_provider_by_id(self, provider_id):
                return self.providers.get(provider_id)

            async def llm_generate(self, **_kwargs):
                observations.append(is_internal_guardrail_call())
                raise RuntimeError("provider failed")

        result = await AstrBotAdapter(Context()).request_llm_text(
            types.SimpleNamespace(unified_msg_origin="platform:message:session"),
            provider_id="review",
            prompt="review",
            system_prompt="audit",
        )

        self.assertFalse(result.success)
        self.assertEqual(observations, [True])
        self.assertFalse(is_internal_guardrail_call())

    async def test_adapter_restores_identity_after_timeout(self):
        observations = []

        class Context:
            providers = {"review": object()}

            def get_provider_by_id(self, provider_id):
                return self.providers.get(provider_id)

            async def llm_generate(self, **_kwargs):
                observations.append(is_internal_guardrail_call())
                await asyncio.sleep(1)

        result = await AstrBotAdapter(Context()).request_llm_text(
            types.SimpleNamespace(unified_msg_origin="platform:message:session"),
            provider_id="review",
            prompt="review",
            system_prompt="audit",
            timeout_seconds=0.001,
        )

        self.assertFalse(result.success)
        self.assertEqual(observations, [True])
        self.assertFalse(is_internal_guardrail_call())

    async def test_provider_fallback_and_retry_both_have_internal_identity(self):
        observations = []

        class Provider:
            async def text_chat(self, **_kwargs):
                observations.append(is_internal_guardrail_call())
                return types.SimpleNamespace(completion_text="safe")

        provider = Provider()

        class Context:
            llm_generate = None
            providers = {"review": provider}

            def get_provider_by_id(self, provider_id):
                return self.providers.get(provider_id)

        adapter = AstrBotAdapter(Context())
        review = await adapter.request_llm_text(
            types.SimpleNamespace(unified_msg_origin="platform:message:session"),
            provider_id="review",
            prompt="review",
            system_prompt="audit",
        )
        retry = await adapter.regenerate_llm_text(
            types.SimpleNamespace(unified_msg_origin="platform:message:session"),
            RetryRequestSnapshot(
                prompt="original",
                system_prompt="system",
                contexts=(),
                extra_user_text_parts=(),
                provider_id="review",
            ),
            "retry",
            timeout_seconds=1,
        )

        self.assertTrue(review.success)
        self.assertTrue(retry.success)
        self.assertEqual(observations, [True, True])
        self.assertFalse(is_internal_guardrail_call())
