"""Small AstrBot compatibility adapter layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AdapterResult:
    success: bool
    warnings: list[str] = field(default_factory=list)


class AstrBotAdapter:
    """Isolate direct AstrBot object mutation from rule logic."""

    def get_umo(self, event: Any) -> str:
        return str(getattr(event, "unified_msg_origin", "") or "")

    def get_event_text(self, event: Any) -> str:
        getter = getattr(event, "get_message_str", None)
        if callable(getter):
            try:
                return str(getter() or "")
            except (AttributeError, TypeError, ValueError):
                pass
        return str(getattr(event, "message_str", "") or "")

    def is_private_chat(self, event: Any) -> bool:
        checker = getattr(event, "is_private_chat", None)
        if callable(checker):
            try:
                return bool(checker())
            except (AttributeError, TypeError, ValueError):
                return False
        return False

    def get_request_prompt(self, request: Any) -> str:
        return str(getattr(request, "prompt", "") or "")

    def set_request_prompt(self, request: Any, text: str) -> AdapterResult:
        try:
            setattr(request, "prompt", text)
        except (AttributeError, TypeError) as exc:
            return AdapterResult(False, [f"failed to set request.prompt: {exc}"])
        return AdapterResult(True)

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

    def apply_route(self, event: Any, request: Any, provider_id: str) -> AdapterResult:
        warnings: list[str] = []
        applied = False
        try:
            setattr(request, "provider_id", provider_id)
            applied = True
        except (AttributeError, TypeError) as exc:
            warnings.append(f"failed to set request.provider_id: {exc}")

        setter = getattr(event, "set_extra", None)
        if callable(setter):
            try:
                setter("selected_provider", provider_id)
                applied = True
            except (AttributeError, TypeError, ValueError) as exc:
                warnings.append(f"failed to set event selected_provider: {exc}")

        if not applied and not warnings:
            warnings.append("no known provider routing hook was available")
        return AdapterResult(applied, warnings)

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
