"""Opt-in bridge for main agents which bypass the normal request hooks.

AstrBot 4.26.x assembles request messages in ToolLoopAgentRunner.reset.
Intercept there, before assembly, rather than reconstructing a request from
on_agent_begin's already assembled messages. No event subclass is assumed.
"""

import inspect
from functools import wraps
from typing import Any, Awaitable, Callable


class AgentRequestEntry:
    def __init__(
        self,
        context: Any,
        main_hooks: Any,
        prepare: Callable[[Any, Any, Any], Awaitable[bool]],
    ) -> None:
        self.context = context
        self.main_hooks = main_hooks
        self.prepare = prepare
        self.active = False
        self.runner_type: type | None = None
        self.original_reset: Any = None
        self.wrapper: Any = None

    def install(self, runner_type: type) -> None:
        if self.active:
            return
        original = runner_type.reset
        owner = getattr(original, "_guardrail_agent_entry_owner", None)
        if owner is not None and owner.active:
            raise RuntimeError("another Guardrail Agent entry is already installed")
        signature = inspect.signature(original)
        required = {"provider", "request", "run_context", "agent_hooks"}
        if not required.issubset(signature.parameters):
            raise RuntimeError("unsupported AstrBot Runner.reset signature")
        for name in ("step", "_transition_state", "get_final_llm_resp"):
            if not callable(getattr(runner_type, name, None)):
                raise RuntimeError(f"unsupported AstrBot Runner: missing {name}")

        @wraps(original)
        async def reset(runner, *args, **kwargs):
            # A previously blocked instance may be explicitly reused for a new
            # request. Restore only the step gate installed by this bridge.
            gate = getattr(runner, "_guardrail_blocked_step", None)
            if gate is not None and getattr(runner, "step", None) is gate:
                runner.step = runner._guardrail_previous_step
                del runner._guardrail_blocked_step
                del runner._guardrail_previous_step
            blocked = False
            if self.active:
                arguments = signature.bind(runner, *args, **kwargs).arguments
                run_context = arguments.get("run_context")
                agent_context = getattr(run_context, "context", None)
                event = getattr(agent_context, "event", None)
                if (
                    event is not None
                    and getattr(agent_context, "context", None) is self.context
                    and arguments.get("agent_hooks") is self.main_hooks
                ):
                    blocked = await self.prepare(
                        event, arguments["request"], arguments["provider"]
                    )
            result = await original(runner, *args, **kwargs)
            if blocked:
                # Stopping the event alone races the host's async stop watcher.
                # Keep this gate on the instance even after plugin unloading.
                async def blocked_step(*_args, **_kwargs):
                    if False:
                        yield None

                runner._guardrail_previous_step = runner.step
                runner._guardrail_blocked_step = blocked_step
                runner.step = blocked_step
                runner.final_llm_resp = None
                runner._transition_state(type(runner._state).DONE)
            return result

        reset._guardrail_agent_entry_owner = self
        self.original_reset = original
        self.wrapper = reset
        self.runner_type = runner_type
        self.active = True
        runner_type.reset = reset

    def uninstall(self) -> None:
        self.active = False
        if self.runner_type is not None and self.runner_type.reset is self.wrapper:
            self.runner_type.reset = self.original_reset
