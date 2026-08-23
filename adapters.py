"""Small AstrBot compatibility adapter layer."""

from __future__ import annotations

import asyncio
import inspect
import re
from dataclasses import dataclass, field
from typing import Any


ROUTE_TARGET_PROVIDER_EXTRA = "_llm_guardrail_target_provider"
ROUTE_SELECTED_PROVIDER_EXTRA = "selected_provider"


@dataclass
class AdapterResult:
    success: bool
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class AstrBotAdapter:
    """Isolate direct AstrBot object mutation from rule logic."""

    def __init__(self, context: Any | None = None) -> None:
        self.context = context

    def get_umo(self, event: Any) -> str:
        return str(getattr(event, "unified_msg_origin", "") or "")

    def get_principal_parts(self, event: Any) -> tuple[str, str] | None:
        """Return AstrBot's platform/user identity without deriving it from UMO.

        UMO represents a conversation and would incorrectly turn an entire
        group into one access-control subject.  Attribute fallbacks keep unit
        tests and older adapters usable, but no fallback ever parses UMO.
        """

        platform_id = self._event_platform_name(event)
        sender_id = self._event_identity_value(
            event,
            method_name="get_sender_id",
            attribute_name="sender_id",
        )
        if not platform_id or not sender_id:
            return None
        return platform_id, sender_id

    @classmethod
    def _event_platform_name(cls, event: Any) -> str:
        """Return the adapter type, not the individual bot/account ID.

        AstrBot exposes both ``get_platform_name()`` (the adapter type such
        as ``aiocqhttp``) and ``get_platform_id()``.  The latter may identify
        a configured bot instance, so using it would split one platform's
        access decisions per bot and make Pages entries unintuitive.  The
        documented event/session metadata provides stable adapter-name
        fallbacks without parsing UMO.
        """

        platform_name = cls._event_identity_value(
            event,
            method_name="get_platform_name",
            attribute_name="platform_name",
        )
        if platform_name:
            return platform_name
        metadata = getattr(event, "platform_meta", None)
        platform_name = str(getattr(metadata, "name", "") or "").strip()
        if platform_name:
            return platform_name
        session = getattr(event, "session", None)
        return str(getattr(session, "platform_name", "") or "").strip()

    @staticmethod
    def _event_identity_value(
        event: Any,
        *,
        method_name: str,
        attribute_name: str,
    ) -> str:
        getter = getattr(event, method_name, None)
        value: Any = None
        if callable(getter):
            try:
                value = getter()
            except (AttributeError, RuntimeError, TypeError, ValueError):
                value = None
        if value is None:
            value = getattr(event, attribute_name, None)
        return str(value if value is not None else "").strip()

    def get_event_text(self, event: Any) -> str:
        getter = getattr(event, "get_message_str", None)
        if callable(getter):
            try:
                text = str(getter() or "")
                if text:
                    return text
            except (AttributeError, TypeError, ValueError):
                pass
        text = str(getattr(event, "message_str", "") or "")
        if text:
            return text

        outline_getter = getattr(event, "get_message_outline", None)
        if callable(outline_getter):
            try:
                text = str(outline_getter() or "")
                if text:
                    return text
            except (AttributeError, TypeError, ValueError):
                pass

        message_obj = getattr(event, "message_obj", None)
        text = str(getattr(message_obj, "message_str", "") or "")
        if text:
            return text

        messages_getter = getattr(event, "get_messages", None)
        components = None
        if callable(messages_getter):
            try:
                components = messages_getter()
            except (AttributeError, TypeError, ValueError):
                components = None
        if components is None:
            components = getattr(message_obj, "message", None)
        if isinstance(components, list):
            parts = []
            for component in components:
                value = getattr(component, "text", None)
                if value:
                    parts.append(str(value))
            if parts:
                return "".join(parts)

        return ""

    def is_private_chat(self, event: Any) -> bool:
        checker = getattr(event, "is_private_chat", None)
        if callable(checker):
            try:
                return bool(checker())
            except (AttributeError, TypeError, ValueError):
                return False
        return False

    def is_admin(self, event: Any) -> bool:
        checker = getattr(event, "is_admin", None)
        if callable(checker):
            try:
                return bool(checker())
            except (AttributeError, TypeError, ValueError):
                return False
        return False

    def is_command_event(self, event: Any) -> bool:
        for text in self._event_text_candidates(event):
            if self._looks_like_slash_command(text):
                return True

        for key in ("command_name", "matched_command", "cmd"):
            value = getattr(event, key, None)
            if isinstance(value, str) and value.strip():
                return True

        getter = getattr(event, "get_extra", None)
        if callable(getter):
            for key in ("command_name", "matched_command", "cmd"):
                try:
                    value = getter(key, "")
                except (AttributeError, TypeError, ValueError):
                    value = ""
                if isinstance(value, str) and value.strip():
                    return True

        text = self.get_event_text(event).strip().lower()
        return self.is_admin(event) and text == "guardrail"

    def is_llm_candidate_event(self, event: Any) -> bool:
        if self.is_command_event(event):
            return False
        if not self.has_input_text(event):
            return False
        marker = getattr(event, "is_at_or_wake_command", None)
        if marker is not None:
            return bool(marker)
        checker = getattr(event, "is_wake_up", None)
        if callable(checker):
            try:
                return bool(checker())
            except (AttributeError, TypeError, ValueError):
                return True
        return True

    def has_input_text(self, event: Any) -> bool:
        """Whether the event contains processable text, excluding outlines."""

        return bool(self._get_event_content_text(event).strip())

    def _event_text_candidates(self, event: Any) -> list[str]:
        candidates: list[str] = []

        for method_name in ("get_message_str", "get_message_outline"):
            getter = getattr(event, method_name, None)
            if callable(getter):
                try:
                    candidates.append(str(getter() or ""))
                except (AttributeError, TypeError, ValueError):
                    pass

        for attr_name in ("message_str", "raw_message"):
            candidates.append(str(getattr(event, attr_name, "") or ""))

        message_obj = getattr(event, "message_obj", None)
        if message_obj is not None:
            for attr_name in ("message_str", "raw_message"):
                candidates.append(str(getattr(message_obj, attr_name, "") or ""))

        return candidates

    def _get_event_content_text(self, event: Any) -> str:
        getter = getattr(event, "get_message_str", None)
        if callable(getter):
            try:
                text = str(getter() or "")
                if text:
                    return text
            except (AttributeError, TypeError, ValueError):
                pass
        text = str(getattr(event, "message_str", "") or "")
        if text:
            return text

        message_obj = getattr(event, "message_obj", None)
        text = str(getattr(message_obj, "message_str", "") or "")
        if text:
            return text

        messages_getter = getattr(event, "get_messages", None)
        components = None
        if callable(messages_getter):
            try:
                components = messages_getter()
            except (AttributeError, TypeError, ValueError):
                components = None
        if components is None:
            components = getattr(message_obj, "message", None)
        if isinstance(components, list):
            parts = []
            for component in components:
                value = getattr(component, "text", None)
                if value:
                    parts.append(str(value))
            if parts:
                return "".join(parts)

        return ""

    @staticmethod
    def _looks_like_slash_command(text: str) -> bool:
        if not text:
            return False
        normalized = re.sub(r"^(?:\s|\[At:[^\]]+\])+", "", str(text))
        return normalized.startswith("/")

    def get_request_prompt(self, request: Any) -> str:
        if request is None:
            return ""
        return str(getattr(request, "prompt", "") or "")

    def set_request_prompt(self, request: Any, text: str) -> AdapterResult:
        if request is None:
            return AdapterResult(False, ["request is unavailable"])
        try:
            setattr(request, "prompt", text)
        except (AttributeError, TypeError) as exc:
            return AdapterResult(False, [f"failed to set request.prompt: {exc}"])
        return AdapterResult(True)

    def set_event_text(self, event: Any, text: str) -> AdapterResult:
        warnings: list[str] = []
        success = False
        try:
            setattr(event, "message_str", text)
            success = True
        except (AttributeError, TypeError) as exc:
            warnings.append(f"failed to set event.message_str: {exc}")

        message_obj = getattr(event, "message_obj", None)
        if message_obj is not None:
            try:
                setattr(message_obj, "message_str", text)
                success = True
            except (AttributeError, TypeError) as exc:
                warnings.append(f"failed to set message_obj.message_str: {exc}")

        return AdapterResult(success, warnings)

    def get_system_prompt(self, request: Any) -> str:
        return str(getattr(request, "system_prompt", "") or "")

    def set_system_prompt(self, request: Any, text: str) -> AdapterResult:
        try:
            setattr(request, "system_prompt", text)
        except (AttributeError, TypeError) as exc:
            return AdapterResult(False, [f"failed to set request.system_prompt: {exc}"])
        return AdapterResult(True)

    def append_temp_user_context(self, request: Any, text: str) -> AdapterResult:
        try:
            from astrbot.core.agent.message import TextPart
        except ImportError as exc:
            return AdapterResult(False, [f"TextPart import failed: {exc}"])

        try:
            part = TextPart(text=text)
            marker = getattr(part, "mark_as_temp", None)
            if callable(marker):
                marker()
            parts = getattr(request, "extra_user_content_parts", None)
            if parts is None:
                parts = []
                setattr(request, "extra_user_content_parts", parts)
            parts.append(part)
        except (AttributeError, TypeError, ValueError) as exc:
            return AdapterResult(
                False, [f"failed to append temp user context: {exc}"]
            )
        return AdapterResult(True)

    async def apply_route(self, event: Any, request: Any, provider_id: str) -> AdapterResult:
        warnings: list[str] = []
        route_target = str(provider_id or "").strip()
        if not route_target:
            return AdapterResult(False, ["route target provider is empty"])

        target_result = self.set_event_extra(
            event,
            ROUTE_TARGET_PROVIDER_EXTRA,
            route_target,
        )
        warnings.extend(target_result.warnings)
        provider_exists = self._provider_exists(route_target)
        if provider_exists is False:
            warnings.append(
                f"route target provider {route_target!r} is unavailable; use default request provider"
            )
            return AdapterResult(
                True,
                warnings,
                {
                    "default_route": True,
                    "route_target": route_target,
                    "unavailable_provider_id": route_target,
                },
            )

        provider_result = self.set_event_extra(
            event, ROUTE_SELECTED_PROVIDER_EXTRA, route_target
        )
        warnings.extend(provider_result.warnings)
        return AdapterResult(True, warnings)

    async def request_llm_text(
        self,
        event: Any,
        provider_id: str,
        prompt: str,
        system_prompt: str,
        timeout_seconds: float = 0.0,
    ) -> AdapterResult:
        if self.context is None:
            return AdapterResult(False, ["llm context is unavailable"])

        target_provider_id = await self._resolve_chat_provider_id(event, provider_id)
        if not target_provider_id:
            return AdapterResult(False, ["llm review provider is unavailable"])

        provider_exists = self._provider_exists(target_provider_id)
        if provider_exists is False:
            return AdapterResult(
                False,
                [f"llm review provider {target_provider_id!r} is unavailable"],
            )

        async def call() -> Any:
            generator = getattr(self.context, "llm_generate", None)
            if callable(generator):
                return await generator(
                    chat_provider_id=target_provider_id,
                    prompt=prompt,
                    system_prompt=system_prompt,
                )
            provider = self._get_provider_by_id(target_provider_id)
            if provider is None:
                return AdapterResult(
                    False,
                    [f"llm review provider {target_provider_id!r} is unavailable"],
                )
            text_chat = getattr(provider, "text_chat", None)
            if not callable(text_chat):
                return AdapterResult(
                    False,
                    [f"llm review provider {target_provider_id!r} has no text_chat"],
                )
            return await text_chat(prompt=prompt, system_prompt=system_prompt, contexts=[])

        try:
            response = (
                await asyncio.wait_for(call(), timeout_seconds)
                if timeout_seconds > 0
                else await call()
            )
        except TimeoutError:
            return AdapterResult(
                False,
                [f"llm review timed out after {timeout_seconds:g}s"],
                {"provider_id": target_provider_id},
            )
        except Exception as exc:
            return AdapterResult(
                False,
                [f"llm review call failed: {type(exc).__name__}: {exc}"],
                {"provider_id": target_provider_id},
            )

        if isinstance(response, AdapterResult):
            response.metadata.setdefault("provider_id", target_provider_id)
            return response

        text = str(getattr(response, "completion_text", "") or "")
        return AdapterResult(
            True,
            metadata={"provider_id": target_provider_id, "text": text},
        )

    async def search_knowledge_base(
        self,
        knowledge_bases: list[str],
        query: str,
        top_k: int,
        timeout_seconds: float = 0.0,
    ) -> AdapterResult:
        if self.context is None:
            return AdapterResult(False, ["knowledge base context is unavailable"])
        kb_manager = getattr(self.context, "kb_manager", None)
        if kb_manager is None:
            return AdapterResult(False, ["knowledge base manager is unavailable"])

        kb_refs = [str(item).strip() for item in knowledge_bases if str(item).strip()]
        if not kb_refs:
            return AdapterResult(False, ["knowledge_bases is empty"])

        try:
            kb_names, helpers = await self._resolve_knowledge_bases(kb_manager, kb_refs)

            async def call() -> Any:
                retriever = getattr(kb_manager, "retrieve", None)
                if callable(retriever):
                    return await self._call_kb_manager_retrieve(
                        retriever, query, kb_names, top_k
                    )
                return await self._call_kb_helpers_retrieve(helpers, query, top_k)

            raw_result = (
                await asyncio.wait_for(call(), timeout_seconds)
                if timeout_seconds > 0
                else await call()
            )
        except TimeoutError:
            return AdapterResult(
                False,
                [f"rag search timed out after {timeout_seconds:g}s"],
                {"knowledge_bases": kb_refs},
            )
        except Exception as exc:
            return AdapterResult(
                False,
                [f"rag search failed: {type(exc).__name__}: {exc}"],
                {"knowledge_bases": kb_refs},
            )

        evidence = self._normalize_kb_evidence(raw_result, top_k)
        return AdapterResult(
            True,
            metadata={
                "evidence": evidence,
                "knowledge_bases": kb_names or kb_refs,
                "raw_result_type": type(raw_result).__name__,
            },
        )

    def has_active_route(self, event: Any) -> bool:
        return bool(self.get_event_extra(event, ROUTE_TARGET_PROVIDER_EXTRA, ""))

    def get_active_route_target(self, event: Any) -> str:
        return str(self.get_event_extra(event, ROUTE_TARGET_PROVIDER_EXTRA, "") or "")

    async def get_current_request_provider_id(self, event: Any) -> str:
        """Return the Provider selected for the event's main request, if known."""

        selected = str(
            self.get_event_extra(event, ROUTE_SELECTED_PROVIDER_EXTRA, "") or ""
        ).strip()
        if selected:
            return selected
        return await self._resolve_chat_provider_id(event, "")

    def _provider_exists(self, provider_id: str) -> bool | None:
        if self.context is None:
            return None
        getter = getattr(self.context, "get_provider_by_id", None)
        if not callable(getter):
            return None
        try:
            return bool(getter(provider_id))
        except Exception:
            return None

    async def _resolve_chat_provider_id(self, event: Any, provider_id: str) -> str:
        configured = str(provider_id or "").strip()
        if configured:
            return configured
        if self.context is None:
            return ""
        umo = self.get_umo(event)
        getter = getattr(self.context, "get_current_chat_provider_id", None)
        if callable(getter):
            try:
                value = getter(umo)
            except TypeError:
                try:
                    value = getter(umo=umo)
                except TypeError:
                    try:
                        value = getter()
                    except (AttributeError, TypeError, ValueError, RuntimeError):
                        value = ""
                except (AttributeError, ValueError, RuntimeError):
                    value = ""
            except (AttributeError, ValueError, RuntimeError):
                value = ""
            try:
                if inspect.isawaitable(value):
                    value = await value
                provider = str(value or "").strip()
                if provider:
                    return provider
            except (AttributeError, TypeError, ValueError, RuntimeError):
                pass
        provider = self._get_using_provider(umo)
        if provider is None:
            return ""
        meta = getattr(provider, "meta", None)
        if callable(meta):
            try:
                metadata = meta()
                provider_id_value = str(getattr(metadata, "id", "") or "").strip()
                if provider_id_value:
                    return provider_id_value
            except (AttributeError, TypeError, ValueError, RuntimeError):
                return ""
        return ""

    def _get_provider_by_id(self, provider_id: str) -> Any | None:
        if self.context is None:
            return None
        getter = getattr(self.context, "get_provider_by_id", None)
        if not callable(getter):
            return None
        try:
            return getter(provider_id)
        except Exception:
            return None

    def _get_using_provider(self, umo: str) -> Any | None:
        if self.context is None:
            return None
        getter = getattr(self.context, "get_using_provider", None)
        if not callable(getter):
            return None
        try:
            return getter(umo=umo)
        except TypeError:
            try:
                return getter(umo)
            except TypeError:
                try:
                    return getter()
                except (AttributeError, TypeError, ValueError, RuntimeError):
                    return None
            except (AttributeError, TypeError, ValueError, RuntimeError):
                return None
        except (AttributeError, ValueError, RuntimeError):
            return None

    async def _resolve_knowledge_bases(
        self, kb_manager: Any, kb_refs: list[str]
    ) -> tuple[list[str], list[Any]]:
        kb_names: list[str] = []
        helpers: list[Any] = []
        for ref in kb_refs:
            helper = await self._maybe_get_kb_by_name(kb_manager, ref)
            if helper is None:
                helper = await self._maybe_get_kb(kb_manager, ref)
            if helper is not None:
                helpers.append(helper)
                name = self._kb_helper_name(helper) or ref
            else:
                name = ref
            if name not in kb_names:
                kb_names.append(name)
        return kb_names, helpers

    async def _maybe_get_kb_by_name(self, kb_manager: Any, kb_name: str) -> Any | None:
        getter = getattr(kb_manager, "get_kb_by_name", None)
        if not callable(getter):
            return None
        try:
            value = getter(kb_name)
            return await value if inspect.isawaitable(value) else value
        except (AttributeError, TypeError, ValueError, RuntimeError):
            return None

    async def _maybe_get_kb(self, kb_manager: Any, kb_id: str) -> Any | None:
        getter = getattr(kb_manager, "get_kb", None)
        if not callable(getter):
            return None
        try:
            value = getter(kb_id)
            return await value if inspect.isawaitable(value) else value
        except (AttributeError, TypeError, ValueError, RuntimeError):
            return None

    @staticmethod
    def _kb_helper_name(helper: Any) -> str:
        kb = getattr(helper, "kb", None)
        return str(getattr(kb, "kb_name", "") or getattr(helper, "kb_name", "") or "")

    async def _call_kb_manager_retrieve(
        self, retriever: Any, query: str, kb_names: list[str], top_k: int
    ) -> Any:
        attempts = (
            {"query": query, "kb_names": kb_names, "top_m_final": top_k},
            {"query": query, "kb_names": kb_names, "top_k": top_k},
            {"query": query, "kb_names": kb_names},
        )
        last_error: Exception | None = None
        for kwargs in attempts:
            try:
                value = retriever(**kwargs)
                return await value if inspect.isawaitable(value) else value
            except TypeError as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        return None

    async def _call_kb_helpers_retrieve(
        self, helpers: list[Any], query: str, top_k: int
    ) -> list[Any]:
        if not helpers:
            raise RuntimeError("knowledge base retrieve API is unavailable")
        collected: list[Any] = []
        for helper in helpers:
            retriever = getattr(helper, "retrieve", None)
            if not callable(retriever):
                continue
            try:
                value = retriever(query=query, top_k=top_k)
            except TypeError:
                value = retriever(query=query, top_m_final=top_k)
            result = await value if inspect.isawaitable(value) else value
            if isinstance(result, dict) and isinstance(result.get("results"), list):
                collected.extend(result["results"])
            elif isinstance(result, list):
                collected.extend(result)
            elif result:
                collected.append(result)
        return collected

    def _normalize_kb_evidence(self, raw_result: Any, top_k: int) -> list[dict[str, Any]]:
        raw_items: list[Any] = []
        context_text = ""
        if isinstance(raw_result, dict):
            context_text = str(raw_result.get("context_text", "") or "")
            results = raw_result.get("results")
            if isinstance(results, list):
                raw_items.extend(results)
                if not results and context_text:
                    raw_items.append({"text": context_text})
            elif results:
                raw_items.append(results)
            elif context_text:
                raw_items.append({"text": context_text})
        elif isinstance(raw_result, list):
            raw_items.extend(raw_result)
        elif raw_result:
            raw_items.append(raw_result)

        evidence: list[dict[str, Any]] = []
        for index, item in enumerate(raw_items):
            normalized = self._normalize_kb_evidence_item(item, index)
            if normalized["text"]:
                evidence.append(normalized)
            if len(evidence) >= top_k:
                break
        return evidence

    def _normalize_kb_evidence_item(self, item: Any, index: int) -> dict[str, Any]:
        if isinstance(item, str):
            return {"text": item, "score": None, "metadata": {"index": index}}

        if isinstance(item, dict):
            text = self._first_text_value(
                item, ("text", "content", "chunk_text", "page_content")
            )
            score = self._first_float_value(
                item,
                ("score", "similarity", "relevance_score", "rerank_score"),
            )
            if score is None:
                distance = self._first_float_value(item, ("distance",))
                if distance is not None:
                    score = max(0.0, 1.0 - distance)
            metadata = {
                key: value
                for key, value in item.items()
                if key not in {"text", "content", "chunk_text", "page_content"}
            }
            metadata["index"] = index
            return {"text": text, "score": score, "metadata": metadata}

        text = self._first_text_value(
            item, ("text", "content", "chunk_text", "page_content")
        )
        score = self._first_float_value(
            item,
            ("score", "similarity", "relevance_score", "rerank_score"),
        )
        return {"text": text, "score": score, "metadata": {"index": index}}

    @staticmethod
    def _first_text_value(source: Any, keys: tuple[str, ...]) -> str:
        for key in keys:
            value = source.get(key) if isinstance(source, dict) else getattr(source, key, "")
            if value:
                return str(value)
        return ""

    @staticmethod
    def _first_float_value(source: Any, keys: tuple[str, ...]) -> float | None:
        for key in keys:
            value = source.get(key) if isinstance(source, dict) else getattr(source, key, None)
            if value is None or value == "":
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return None

    def get_response_text(self, response: Any) -> str:
        return str(getattr(response, "completion_text", "") or "")

    def set_response_text(self, response: Any, text: str) -> AdapterResult:
        try:
            setattr(response, "completion_text", text)
        except (AttributeError, TypeError) as exc:
            return AdapterResult(False, [f"failed to set response.completion_text: {exc}"])
        return AdapterResult(True)

    def stop_event(self, event: Any) -> AdapterResult:
        stopper = getattr(event, "stop_event", None)
        if not callable(stopper):
            return AdapterResult(False, ["event.stop_event is unavailable"])
        try:
            stopper()
        except (AttributeError, TypeError, ValueError) as exc:
            return AdapterResult(False, [f"event.stop_event failed: {exc}"])
        return AdapterResult(True)

    def set_block_result(self, event: Any, text: str) -> AdapterResult:
        warnings: list[str] = []
        setter = getattr(event, "set_result", None)
        if not callable(setter):
            warnings.append("event.set_result is unavailable")
            stop_result = self.stop_event(event)
            warnings.extend(stop_result.warnings)
            return AdapterResult(False, warnings)

        result_value: Any = text
        plain_result = getattr(event, "plain_result", None)
        if callable(plain_result):
            try:
                result_value = plain_result(text)
            except (AttributeError, TypeError, ValueError) as exc:
                warnings.append(f"event.plain_result failed; using raw text: {exc}")
                result_value = text

        try:
            setter(result_value)
        except (AttributeError, TypeError, ValueError) as exc:
            warnings.append(f"event.set_result failed: {exc}")
            stop_result = self.stop_event(event)
            warnings.extend(stop_result.warnings)
            return AdapterResult(False, warnings)

        stop_result = self.stop_event(event)
        warnings.extend(stop_result.warnings)
        return AdapterResult(stop_result.success, warnings)

    def set_event_extra(self, event: Any, key: str, value: Any) -> AdapterResult:
        setter = getattr(event, "set_extra", None)
        if callable(setter):
            try:
                setter(key, value)
                return AdapterResult(True)
            except (AttributeError, TypeError, ValueError) as exc:
                return AdapterResult(False, [f"event.set_extra failed: {exc}"])
        try:
            setattr(event, key, value)
        except (AttributeError, TypeError) as exc:
            return AdapterResult(False, [f"failed to setattr event extra {key}: {exc}"])
        return AdapterResult(True)

    def get_event_extra(self, event: Any, key: str, default: Any = None) -> Any:
        getter = getattr(event, "get_extra", None)
        if callable(getter):
            try:
                return getter(key, default)
            except (AttributeError, TypeError, ValueError):
                return default
        return getattr(event, key, default)
