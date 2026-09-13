"""Shared constants for LLM Guardrail."""

GUARDRAIL_ACCESS_GATE_PRIORITY = 1_000_000
GUARDRAIL_WAITING_RAILS_PRIORITY = -1_000_000
GUARDRAIL_REQUEST_PRIORITY = -1_000_000
GUARDRAIL_RESPONSE_PRIORITY = 1_000_000

REQUEST_ENTRY_LLM_REQUEST = "llm_request"
REQUEST_ENTRY_AGENT_RESET = "agent_reset"
REQUEST_ENTRY_UNAVAILABLE = "unavailable"
REQUEST_ENTRY_VALUES = frozenset(
    (REQUEST_ENTRY_LLM_REQUEST, REQUEST_ENTRY_AGENT_RESET)
)


def normalize_request_entry(value: object) -> str:
    """Return one stable request-entry value for policy and monitoring use."""

    entry = str(value or "").strip()
    return entry if entry in REQUEST_ENTRY_VALUES else REQUEST_ENTRY_UNAVAILABLE
