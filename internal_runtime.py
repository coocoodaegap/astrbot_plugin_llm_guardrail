"""Task-local identity for model calls owned by LLM Guardrail."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar


_INTERNAL_CALL_DEPTH: ContextVar[int] = ContextVar(
    "llm_guardrail_internal_call_depth",
    default=0,
)


def is_internal_guardrail_call() -> bool:
    """Return whether the current async call chain is Guardrail-owned."""

    return _INTERNAL_CALL_DEPTH.get() > 0


@contextmanager
def internal_guardrail_call() -> Iterator[None]:
    """Establish a nestable internal identity and restore it transactionally."""

    token = _INTERNAL_CALL_DEPTH.set(_INTERNAL_CALL_DEPTH.get() + 1)
    try:
        yield
    finally:
        _INTERNAL_CALL_DEPTH.reset(token)
