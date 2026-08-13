"""Small AstrBot compatibility adapter layer."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any


ROUTE_PREVIOUS_PROVIDER_EXTRA = "_llm_guardrail_previous_provider"
ROUTE_TARGET_PROVIDER_EXTRA = "_llm_guardrail_target_provider"


@dataclass
class AdapterResult:
    success: bool
    warnings: list[str] = field(default_factory=list)


class AstrBotAdapter:
    """Isolate direct AstrBot object mutation from rule logic."""

    def __init__(self, context: Any | None = None) -> None:
        self.context = context

    def get_umo(self, event: Any) -> str:
        return str(getattr(event, "unified_msg_origin", "") or "")

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

    def is_llm_candidate_event(self, event: Any) -> bool:
        text = self.get_event_text(event).strip()
        if text.startswith("/"):
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
        if self.context is None:
            return AdapterResult(False, ["AstrBot context is unavailable for routing"])

        umo = self.get_umo(event)
        previous_provider_id = await self._get_current_chat_provider_id(umo)
        if previous_provider_id:
            previous_result = self.set_event_extra(
                event, ROUTE_PREVIOUS_PROVIDER_EXTRA, previous_provider_id
            )
            warnings.extend(previous_result.warnings)
        target_result = self.set_event_extra(
            event, ROUTE_TARGET_PROVIDER_EXTRA, provider_id
        )
        warnings.extend(target_result.warnings)

        provider_manager = getattr(self.context, "provider_manager", None)
        setter = getattr(provider_manager, "set_provider", None)
        if not callable(setter):
            warnings.append("context.provider_manager.set_provider is unavailable")
            return AdapterResult(False, warnings)

        try:
            from astrbot.core.provider.entities import ProviderType
        except ImportError as exc:
            warnings.append(f"ProviderType import failed: {exc}")
            return AdapterResult(False, warnings)

        try:
            result = setter(provider_id, ProviderType.CHAT_COMPLETION, umo=umo)
            if inspect.isawaitable(result):
                await result
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            warnings.append(f"provider_manager.set_provider failed: {exc}")
            return AdapterResult(False, warnings)

        return AdapterResult(True, warnings)

    async def restore_route(self, event: Any) -> AdapterResult:
        previous_provider_id = self.get_event_extra(
            event, ROUTE_PREVIOUS_PROVIDER_EXTRA, ""
        )
        target_provider_id = self.get_event_extra(event, ROUTE_TARGET_PROVIDER_EXTRA, "")
        if not previous_provider_id or not target_provider_id:
            return AdapterResult(True)
        if previous_provider_id == target_provider_id:
            return AdapterResult(True)
        if self.context is None:
            return AdapterResult(False, ["AstrBot context is unavailable for route restore"])

        warnings: list[str] = []
        provider_manager = getattr(self.context, "provider_manager", None)
        setter = getattr(provider_manager, "set_provider", None)
        if not callable(setter):
            return AdapterResult(False, ["context.provider_manager.set_provider is unavailable"])

        try:
            from astrbot.core.provider.entities import ProviderType
        except ImportError as exc:
            return AdapterResult(False, [f"ProviderType import failed: {exc}"])

        try:
            result = setter(
                str(previous_provider_id),
                ProviderType.CHAT_COMPLETION,
                umo=self.get_umo(event),
            )
            if inspect.isawaitable(result):
                await result
        except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
            warnings.append(f"provider_manager route restore failed: {exc}")
            return AdapterResult(False, warnings)
        return AdapterResult(True, warnings)

    def has_active_route(self, event: Any) -> bool:
        return bool(self.get_event_extra(event, ROUTE_TARGET_PROVIDER_EXTRA, ""))

    def get_active_route_target(self, event: Any) -> str:
        return str(self.get_event_extra(event, ROUTE_TARGET_PROVIDER_EXTRA, "") or "")

    async def _get_current_chat_provider_id(self, umo: str) -> str:
        getter = getattr(self.context, "get_current_chat_provider_id", None)
        if callable(getter):
            try:
                result = getter(umo)
                if inspect.isawaitable(result):
                    result = await result
                return str(result or "")
            except (AttributeError, TypeError, ValueError, RuntimeError):
                return ""

        provider_getter = getattr(self.context, "get_using_provider", None)
        if callable(provider_getter):
            try:
                provider = provider_getter(umo)
                meta = provider.meta() if provider and callable(getattr(provider, "meta", None)) else None
                return str(getattr(meta, "id", "") or "")
            except (AttributeError, TypeError, ValueError, RuntimeError):
                return ""
        return ""

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
