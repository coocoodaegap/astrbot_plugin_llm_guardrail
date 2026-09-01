"""Small AstrBot compatibility adapter layer."""

from __future__ import annotations

import asyncio
import copy
import inspect
import json
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


ROUTE_TARGET_PROVIDER_EXTRA = "_llm_guardrail_target_provider"
ROUTE_SELECTED_PROVIDER_EXTRA = "selected_provider"
VIDEO_FILE_EXTENSIONS = frozenset(
    {"3gp", "avi", "flv", "m4v", "mkv", "mov", "mp4", "mpeg", "mpg", "ts", "webm", "wmv"}
)


@dataclass
class AdapterResult:
    success: bool
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def _elapsed_milliseconds(started_at: float) -> int:
    return max(int((time.monotonic() - started_at) * 1000), 0)


@dataclass(frozen=True)
class RetryRequestSnapshot:
    """A replay-safe subset of one final ProviderRequest.

    The snapshot intentionally excludes media, tools, and opaque temporary
    parts.  P3's first retry implementation only replays plain text requests.
    """

    prompt: str
    system_prompt: str
    contexts: tuple[Any, ...]
    extra_user_text_parts: tuple[str, ...]
    provider_id: str
    provider_source: str = "unavailable"
    unsupported_reason: str = ""

    @property
    def replayable(self) -> bool:
        return not self.unsupported_reason


@dataclass(frozen=True)
class MessageComponentFact:
    """A safe, platform-neutral fact extracted from one message component."""

    index: int
    kind: str
    target_id: str = ""
    plain_text: str = ""
    media_category: str = ""


@dataclass(frozen=True)
class MessageFactSnapshot:
    """Read-only Step 1 facts for policy-local message components."""

    request_user_id: str
    components: tuple[MessageComponentFact, ...]
    message_chain_available: bool
    outline_available: bool
    raw_component_count: int = 0


@dataclass(frozen=True)
class MessageIngressProfile:
    """One safe, immutable representation used to admit an input event."""

    text: str
    has_content: bool
    source: str
    message_facts: MessageFactSnapshot


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
        user_id = self._event_identity_value(
            event,
            method_name="get_sender_id",
            attribute_name="sender_id",
        )
        if not platform_id or not user_id:
            return None
        return platform_id, user_id

    def get_message_fact_snapshot(
        self, event: Any, *, warn_if_unavailable: bool = True
    ) -> AdapterResult:
        """Return P2 message facts without exposing raw platform objects.

        The official message chain is preferred.  A missing or malformed chain
        is a non-fatal compatibility condition: matching components simply see
        no facts and the calling hook can continue normally.
        """

        warnings: list[str] = []
        components, available = self._event_message_components(event, warnings)
        facts: list[MessageComponentFact] = []
        unknown_component_types: set[str] = set()
        for index, component in enumerate(components):
            kind = self._message_component_kind(component)
            if not kind:
                unknown_component_types.add(type(component).__name__)
                continue
            target_id = ""
            plain_text = ""
            media_category = ""
            if kind == "at":
                target_id = self._message_component_value(
                    component, ("qq", "user_id", "target")
                )
            elif kind == "plain":
                plain_text = self._message_component_value(component, ("text",))
            elif kind == "file":
                media_category = self._message_component_media_category(component)
            facts.append(
                MessageComponentFact(
                    index=index,
                    kind=kind,
                    target_id=target_id,
                    plain_text=plain_text,
                    media_category=media_category,
                )
            )

        outline_available = False
        outline_getter = getattr(event, "get_message_outline", None)
        if callable(outline_getter):
            try:
                outline_getter()
                outline_available = True
            except (AttributeError, RuntimeError, TypeError, ValueError):
                warnings.append("message outline is unavailable")

        if not available and warn_if_unavailable:
            warnings.append("message component chain is unavailable")
        elif unknown_component_types:
            warnings.append(
                "unrecognized message component types: "
                + ", ".join(sorted(unknown_component_types)[:4])
            )
        snapshot = MessageFactSnapshot(
            request_user_id=self._event_identity_value(
                event,
                method_name="get_sender_id",
                attribute_name="sender_id",
            ),
            components=tuple(facts),
            message_chain_available=available,
            outline_available=outline_available,
            raw_component_count=len(components),
        )
        return AdapterResult(True, warnings, {"message_fact_snapshot": snapshot})

    def get_message_ingress_profile(self, event: Any) -> AdapterResult:
        """Classify input once without treating an outline as user prose.

        The profile's ``text`` keeps normal text or AstrBot's safe outline when
        available.  A component-only chain without either gets canonical
        ``[ComponentType.*]`` markers, so it remains an input to Rail 1 but
        never exposes attachment paths, URLs, or media content.
        """

        fact_result = self.get_message_fact_snapshot(
            event, warn_if_unavailable=False
        )
        snapshot = fact_result.metadata["message_fact_snapshot"]
        text = self.get_event_text(event).strip()
        if text:
            profile = MessageIngressProfile(text, True, "event_text", snapshot)
        else:
            plain_text = "".join(
                component.plain_text
                for component in snapshot.components
                if component.kind == "plain" and component.plain_text
            ).strip()
            if plain_text:
                profile = MessageIngressProfile(
                    plain_text, True, "plain_component", snapshot
                )
            else:
                markers = self._safe_component_markers(snapshot)
                profile = MessageIngressProfile(
                    markers,
                    bool(markers),
                    "component_markers" if markers else "empty",
                    snapshot,
                )
        fact_result.metadata["message_ingress_profile"] = profile
        return fact_result

    @staticmethod
    def _safe_component_markers(snapshot: MessageFactSnapshot) -> str:
        """Represent non-text components without exposing their payloads."""

        markers = [
            f"[ComponentType.{component.kind.title()}]"
            for component in snapshot.components[:32]
        ]
        if not markers and snapshot.raw_component_count:
            markers.append("[ComponentType.Unknown]")
        return " ".join(markers)

    @staticmethod
    def _event_message_components(
        event: Any, warnings: list[str]
    ) -> tuple[list[Any], bool]:
        getter = getattr(event, "get_messages", None)
        raw_components: Any = None
        available = False
        if callable(getter):
            try:
                raw_components = getter()
                available = raw_components is not None
            except (AttributeError, RuntimeError, TypeError, ValueError):
                warnings.append("failed to read message component chain")
        if raw_components is None:
            message_obj = getattr(event, "message_obj", None)
            raw_components = getattr(message_obj, "message", None)
            available = raw_components is not None
        components = AstrBotAdapter._coerce_message_component_list(raw_components)
        if components is not None:
            return components, available
        if raw_components is not None:
            warnings.append("message component chain has an unsupported shape")
        return [], False

    @staticmethod
    def _coerce_message_component_list(value: Any) -> list[Any] | None:
        """Accept documented lists plus compatible MessageChain containers."""

        if isinstance(value, (list, tuple)):
            return list(value)
        if value is None or isinstance(value, (str, bytes, bytearray, Mapping)):
            return None
        for attribute_name in ("chain", "components", "message"):
            try:
                nested = getattr(value, attribute_name, None)
            except (AttributeError, RuntimeError, TypeError, ValueError):
                nested = None
            if isinstance(nested, (list, tuple)):
                return list(nested)
        try:
            return list(iter(value))
        except (TypeError, RuntimeError, ValueError):
            return None

    @staticmethod
    def _message_component_kind(component: Any) -> str:
        aliases = {
            "plain": "plain",
            "text": "plain",
            "at": "at",
            "forward": "forward",
            "node": "forward",
            "nodes": "forward",
            "file": "file",
            "image": "image",
            "record": "record",
            "video": "video",
            "poke": "poke",
            "face": "face",
            "reply": "reply",
        }
        values = [type(component).__name__]
        if isinstance(component, Mapping):
            values.extend(
                component.get(key)
                for key in ("type", "component_type", "message_type")
            )
        else:
            for attribute_name in ("type", "component_type", "message_type"):
                try:
                    values.append(getattr(component, attribute_name, None))
                except (AttributeError, RuntimeError, TypeError, ValueError):
                    continue
        for value in values:
            normalized = re.sub(r"[^a-z]", "", str(value or "").casefold())
            if normalized in aliases:
                return aliases[normalized]
            for suffix in ("component", "segment", "message"):
                if normalized.endswith(suffix):
                    candidate = normalized.removesuffix(suffix)
                    if candidate in aliases:
                        return aliases[candidate]
        return ""

    @staticmethod
    def _message_component_value(component: Any, names: tuple[str, ...]) -> str:
        for name in names:
            if isinstance(component, Mapping):
                value = component.get(name)
            else:
                try:
                    value = getattr(component, name, None)
                except (AttributeError, RuntimeError, TypeError, ValueError):
                    value = None
            if value is not None:
                value_text = str(value).strip()
                if value_text:
                    return value_text
        return ""

    @classmethod
    def _message_component_media_category(cls, component: Any) -> str:
        """Classify File metadata without retaining paths, names, or URLs."""

        mime_type = cls._message_component_value(
            component, ("mime_type", "mime", "content_type")
        ).casefold()
        if mime_type.startswith("video/"):
            return "video"
        for attribute_name in ("name", "filename", "file_name", "file", "url"):
            suffix = cls._safe_file_suffix(
                cls._message_component_value(component, (attribute_name,))
            )
            if suffix in VIDEO_FILE_EXTENSIONS:
                return "video"
        return ""

    @staticmethod
    def _safe_file_suffix(value: str) -> str:
        """Extract a short extension locally, never expose the source value."""

        filename = str(value or "").split("?", 1)[0].split("#", 1)[0]
        filename = filename.replace("\\", "/").rsplit("/", 1)[-1]
        _stem, dot, suffix = filename.rpartition(".")
        normalized = suffix.casefold()
        if not dot or not re.fullmatch(r"[a-z0-9]{1,10}", normalized):
            return ""
        return normalized

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

    async def get_current_conversation_history(self, event: Any) -> AdapterResult:
        """Read the current AstrBot branch without creating or changing it."""

        if self.context is None:
            return AdapterResult(False, ["conversation context is unavailable"])
        manager = getattr(self.context, "conversation_manager", None)
        if manager is None:
            return AdapterResult(False, ["conversation manager is unavailable"])
        umo = self.get_umo(event)
        if not umo:
            return AdapterResult(False, ["conversation UMO is unavailable"])
        get_current_id = getattr(manager, "get_curr_conversation_id", None)
        get_conversation = getattr(manager, "get_conversation", None)
        if not callable(get_current_id) or not callable(get_conversation):
            return AdapterResult(False, ["conversation manager API is unavailable"])
        try:
            conversation_id = get_current_id(umo)
            if inspect.isawaitable(conversation_id):
                conversation_id = await conversation_id
            conversation_id = str(conversation_id or "").strip()
            if not conversation_id:
                return AdapterResult(False, ["current conversation is unavailable"])
            try:
                conversation = get_conversation(
                    umo, conversation_id, create_if_not_exists=False
                )
            except TypeError:
                # Older AstrBot versions expose the same read API without the
                # explicit non-creating keyword.
                conversation = get_conversation(umo, conversation_id)
            if inspect.isawaitable(conversation):
                conversation = await conversation
        except Exception as exc:
            return AdapterResult(
                False,
                [f"conversation history read failed: {type(exc).__name__}"],
            )

        if conversation is None:
            return AdapterResult(False, ["current conversation is unavailable"])
        raw_history = getattr(conversation, "history", None)
        if not isinstance(raw_history, str):
            return AdapterResult(False, ["conversation history is unavailable"])
        try:
            history = json.loads(raw_history)
        except (TypeError, ValueError):
            return AdapterResult(False, ["conversation history is malformed"])
        if not isinstance(history, list):
            return AdapterResult(False, ["conversation history is malformed"])
        return AdapterResult(
            True,
            metadata={
                "umo": umo,
                "conversation_id": conversation_id,
                "history": history,
            },
        )

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

    async def capture_retry_request_snapshot(
        self, event: Any, request: Any
    ) -> AdapterResult:
        """Capture the final request form needed by P3 output regeneration.

        Saving a deep-copied, limited snapshot prevents later request mutations
        from changing a retry.  Unsupported request shapes are retained as a
        non-replayable snapshot so they can fail closed only if retry is asked
        for; the ordinary main request remains unaffected.
        """

        if request is None:
            return AdapterResult(False, ["retry request snapshot is unavailable"])

        prompt = str(getattr(request, "prompt", "") or "")
        system_prompt = str(getattr(request, "system_prompt", "") or "")
        unsupported_reason = ""
        raw_contexts = getattr(request, "contexts", [])
        if raw_contexts is None:
            raw_contexts = []
        if not isinstance(raw_contexts, (list, tuple)):
            unsupported_reason = "request contexts are not replayable"
            contexts: tuple[Any, ...] = ()
        else:
            try:
                contexts = tuple(copy.deepcopy(raw_contexts))
            except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
                unsupported_reason = (
                    "request contexts cannot be copied "
                    f"({type(exc).__name__})"
                )
                contexts = ()

        if not unsupported_reason and not self._contexts_are_text_replayable(contexts):
            unsupported_reason = "request contexts contain non-text content"

        extra_user_text_parts: tuple[str, ...] = ()
        if not unsupported_reason:
            extra_user_text_parts, unsupported_reason = self._text_extra_parts(
                getattr(request, "extra_user_content_parts", None)
            )
        if not unsupported_reason and self._has_request_values(
            getattr(request, "image_urls", None)
        ):
            unsupported_reason = "request has image URLs"
        if not unsupported_reason and self._has_request_values(
            getattr(request, "tools", None)
        ):
            unsupported_reason = "request has tools"

        provider_id = self._request_provider_id(request)
        provider_source = "provider_request" if provider_id else ""
        if not provider_id:
            provider_id = self.get_selected_request_provider_id(event)
            provider_source = "event_selected_provider" if provider_id else ""
        if not provider_id:
            provider_id = await self.get_current_chat_provider_id(event)
            provider_source = "current_chat_provider" if provider_id else "unavailable"
        snapshot = RetryRequestSnapshot(
            prompt=prompt,
            system_prompt=system_prompt,
            contexts=contexts,
            extra_user_text_parts=extra_user_text_parts,
            provider_id=provider_id,
            provider_source=provider_source,
            unsupported_reason=unsupported_reason,
        )
        return AdapterResult(True, metadata={"snapshot": snapshot})

    async def regenerate_llm_text(
        self,
        event: Any,
        snapshot: RetryRequestSnapshot,
        prompt: str,
        *,
        timeout_seconds: float,
    ) -> AdapterResult:
        """Call the selected Provider directly for one plain-text retry.

        This deliberately does not use ``Context.llm_generate``: a retry
        generated inside ``on_llm_response`` must not re-enter the complete
        AstrBot hook chain and emit another user-facing response.
        """

        if not snapshot.replayable:
            return AdapterResult(
                False,
                [
                    "retry generation cannot replay this request: "
                    f"{snapshot.unsupported_reason}"
                ],
                {
                    "provider_id": snapshot.provider_id,
                    "provider_source": snapshot.provider_source,
                    "elapsed_ms": 0,
                },
            )

        provider = self._get_provider_by_id(snapshot.provider_id)
        provider_source = snapshot.provider_source
        if provider is None:
            return AdapterResult(
                False,
                ["retry generation provider is unavailable"],
                {
                    "provider_id": snapshot.provider_id,
                    "provider_source": provider_source,
                    "elapsed_ms": 0,
                },
            )
        try:
            text_chat = getattr(provider, "text_chat", None)
        except Exception as exc:
            return AdapterResult(
                False,
                [f"retry generation provider interface failed: {type(exc).__name__}"],
                {
                    "provider_id": snapshot.provider_id,
                    "provider_source": provider_source,
                    "elapsed_ms": 0,
                },
            )
        if not callable(text_chat):
            return AdapterResult(
                False,
                ["retry generation provider has no text_chat"],
                {
                    "provider_id": snapshot.provider_id,
                    "provider_source": provider_source,
                    "elapsed_ms": 0,
                },
            )

        async def call() -> Any:
            kwargs = {
                "prompt": prompt,
                "context": list(copy.deepcopy(snapshot.contexts)),
                "system_prompt": snapshot.system_prompt,
            }
            try:
                value = text_chat(**kwargs)
            except TypeError as exc:
                # Older / third-party Providers sometimes use the plural
                # spelling.  The official SDK documents ``context``; keep the
                # compatibility branch inside the adapter rather than Rails.
                if "context" not in str(exc):
                    raise
                kwargs["contexts"] = kwargs.pop("context")
                value = text_chat(**kwargs)
            return await value if inspect.isawaitable(value) else value

        started_at = time.monotonic()
        try:
            response = await asyncio.wait_for(call(), timeout_seconds)
        except TimeoutError:
            return AdapterResult(
                False,
                [f"retry generation timed out after {timeout_seconds:g}s"],
                {
                    "provider_id": snapshot.provider_id,
                    "provider_source": provider_source,
                    "elapsed_ms": _elapsed_milliseconds(started_at),
                },
            )
        except asyncio.CancelledError:
            return AdapterResult(
                False,
                ["retry generation was cancelled"],
                {
                    "provider_id": snapshot.provider_id,
                    "provider_source": provider_source,
                    "elapsed_ms": _elapsed_milliseconds(started_at),
                },
            )
        except Exception as exc:
            return AdapterResult(
                False,
                [f"retry generation failed: {type(exc).__name__}"],
                {
                    "provider_id": snapshot.provider_id,
                    "provider_source": provider_source,
                    "elapsed_ms": _elapsed_milliseconds(started_at),
                },
            )

        try:
            text = getattr(response, "completion_text", None)
        except Exception as exc:
            return AdapterResult(
                False,
                [f"retry generation response read failed: {type(exc).__name__}"],
                {
                    "provider_id": snapshot.provider_id,
                    "provider_source": provider_source,
                    "elapsed_ms": _elapsed_milliseconds(started_at),
                },
            )
        if not isinstance(text, str) or not text.strip():
            return AdapterResult(
                False,
                ["retry generation returned no text"],
                {
                    "provider_id": snapshot.provider_id,
                    "provider_source": provider_source,
                    "elapsed_ms": _elapsed_milliseconds(started_at),
                },
            )
        return AdapterResult(
            True,
            metadata={
                "provider_id": snapshot.provider_id,
                "provider_source": provider_source,
                "elapsed_ms": _elapsed_milliseconds(started_at),
                "text": text,
            },
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

    def get_selected_request_provider_id(self, event: Any) -> str:
        """Return an explicit Provider selected for this event, without fallback."""

        return str(
            self.get_event_extra(event, ROUTE_SELECTED_PROVIDER_EXTRA, "") or ""
        ).strip()

    async def get_current_request_provider_id(self, event: Any) -> str:
        """Return the Provider selected for the event's main request, if known."""

        selected = self.get_selected_request_provider_id(event)
        if selected:
            return selected
        return await self.get_current_chat_provider_id(event)

    async def get_current_chat_provider_id(self, event: Any) -> str:
        """Return AstrBot's current chat Provider without Guardrail route extras.

        Keeping this separate from :meth:`get_current_request_provider_id`
        prevents a route-policy's ``selected_provider`` marker from being
        mistaken for the session's current Provider.
        """

        return await self._resolve_chat_provider_id(event, "")

    @staticmethod
    def _has_request_values(value: Any) -> bool:
        if value is None:
            return False
        try:
            return bool(value)
        except (AttributeError, TypeError, ValueError):
            # An opaque request field cannot be safely replayed as text.
            return True

    @staticmethod
    def _text_extra_parts(value: Any) -> tuple[tuple[str, ...], str]:
        """Extract only text-shaped temporary request content for P3 replay."""

        if value is None:
            return (), ""
        if not isinstance(value, (list, tuple)):
            return (), "request temporary content parts are not replayable"
        texts: list[str] = []
        for part in value:
            if isinstance(part, str):
                texts.append(part)
                continue
            if isinstance(part, Mapping):
                part_type = str(part.get("type", "text") or "text").strip().lower()
                text = part.get("text")
            else:
                part_type = str(getattr(part, "type", "text") or "text").strip().lower()
                text = getattr(part, "text", None)
            if part_type not in {"text", "textpart"} or not isinstance(text, str):
                return (), "request has non-text temporary content parts"
            texts.append(text)
        return tuple(texts), ""

    @classmethod
    def _contexts_are_text_replayable(cls, contexts: tuple[Any, ...]) -> bool:
        """Accept only OpenAI-style context messages carrying text content."""

        unsupported_keys = {
            "tool_calls",
            "function_call",
            "tool_call",
            "tool",
            "image_url",
            "image_urls",
            "image",
            "attachments",
            "files",
            "file",
            "input_file",
            "audio",
            "input_audio",
            "video",
            "input_video",
            "media",
        }
        allowed_message_keys = {"role", "content", "name"}
        allowed_content_part_keys = {"type", "text"}
        for message in contexts:
            if not isinstance(message, Mapping):
                return False
            if any(key not in allowed_message_keys for key in message):
                return False
            role_value = message.get("role")
            if not isinstance(role_value, str):
                return False
            role = role_value.strip().lower()
            if role in {"tool", "function"}:
                return False
            if any(cls._has_request_values(message.get(key)) for key in unsupported_keys):
                return False
            if "name" in message and not isinstance(message.get("name"), str):
                return False
            content = message.get("content")
            if isinstance(content, str):
                continue
            if not isinstance(content, list):
                return False
            for part in content:
                if not isinstance(part, Mapping):
                    return False
                if any(key not in allowed_content_part_keys for key in part):
                    return False
                if any(
                    cls._has_request_values(part.get(key))
                    for key in unsupported_keys
                ):
                    return False
                part_type = str(part.get("type", "") or "").strip().lower()
                text = part.get("text")
                if part_type not in {"text", "input_text", "output_text"} or not isinstance(
                    text, str
                ):
                    return False
        return True

    @staticmethod
    def _request_provider_id(request: Any) -> str:
        """Read only an explicit ProviderRequest provider ID when exposed."""

        try:
            return str(getattr(request, "provider_id", "") or "").strip()
        except (AttributeError, TypeError, ValueError):
            return ""

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
            nested_metadata = item.get("metadata")
            if isinstance(nested_metadata, dict):
                for key in ("kb_id", "kb_name", "doc_id", "doc_name"):
                    if key not in metadata and nested_metadata.get(key) is not None:
                        metadata[key] = nested_metadata[key]
            metadata["index"] = index
            return {"text": text, "score": score, "metadata": metadata}

        text = self._first_text_value(
            item, ("text", "content", "chunk_text", "page_content")
        )
        score = self._first_float_value(
            item,
            ("score", "similarity", "relevance_score", "rerank_score"),
        )
        metadata: dict[str, Any] = {"index": index}
        for key in ("kb_id", "kb_name", "doc_id", "doc_name"):
            value = getattr(item, key, None)
            if value is not None:
                metadata[key] = value
        nested_metadata = getattr(item, "metadata", None)
        if isinstance(nested_metadata, dict):
            for key in ("kb_id", "kb_name", "doc_id", "doc_name"):
                if key not in metadata and nested_metadata.get(key) is not None:
                    metadata[key] = nested_metadata[key]
        return {"text": text, "score": score, "metadata": metadata}

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

    def read_response_text(self, response: Any) -> AdapterResult:
        """Read a response text field without letting adapter errors escape."""

        try:
            text = str(getattr(response, "completion_text", "") or "")
        except Exception as exc:
            return AdapterResult(
                False,
                [f"failed to read response.completion_text: {type(exc).__name__}"],
            )
        return AdapterResult(True, metadata={"text": text})

    def get_response_text(self, response: Any) -> str:
        result = self.read_response_text(response)
        return str(result.metadata.get("text", "") or "")

    def can_set_response_text(self, response: Any) -> bool:
        """Conservatively preflight the writable response field for P3 retry."""

        if response is None:
            return False
        try:
            descriptor = inspect.getattr_static(type(response), "completion_text", None)
            if isinstance(descriptor, property) and descriptor.fset is None:
                return False
            getattr(response, "completion_text")
        except Exception:
            return False
        return True

    def set_response_text(self, response: Any, text: str) -> AdapterResult:
        try:
            setattr(response, "completion_text", text)
        except Exception as exc:
            return AdapterResult(
                False,
                [f"failed to set response.completion_text: {type(exc).__name__}"],
            )
        return AdapterResult(True)

    async def send_text_result(self, event: Any, text: str) -> AdapterResult:
        """Send a final plain-text result directly from an agent-done hook."""

        sender = getattr(event, "send", None)
        if not callable(sender):
            return AdapterResult(False, ["event.send is unavailable"])
        result_value: Any = text
        plain_result = getattr(event, "plain_result", None)
        if callable(plain_result):
            try:
                result_value = plain_result(text)
            except Exception as exc:
                return AdapterResult(
                    False, [f"event.plain_result failed: {type(exc).__name__}"]
                )
        try:
            value = sender(result_value)
            if inspect.isawaitable(value):
                await value
        except Exception as exc:
            return AdapterResult(False, [f"event.send failed: {type(exc).__name__}"])
        return AdapterResult(True)

    def replace_final_assistant_message(
        self, run_context: Any, text: str
    ) -> AdapterResult:
        """Replace the last persisted assistant text before AstrBot saves history."""

        messages = getattr(run_context, "messages", None)
        if not isinstance(messages, list):
            return AdapterResult(False, ["agent run context messages are unavailable"])
        for message in reversed(messages):
            role = (
                message.get("role")
                if isinstance(message, dict)
                else getattr(message, "role", None)
            )
            if role != "assistant":
                continue
            try:
                if isinstance(message, dict):
                    message["content"] = text
                else:
                    setattr(message, "content", text)
            except Exception as exc:
                return AdapterResult(
                    False,
                    [
                        "failed to replace final assistant history message: "
                        f"{type(exc).__name__}"
                    ],
                )
            return AdapterResult(True)
        return AdapterResult(False, ["final assistant history message is unavailable"])

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
