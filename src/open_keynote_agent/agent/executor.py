from __future__ import annotations

from typing import Callable

from open_keynote_agent.agent.registry import ToolRegistry
from open_keynote_agent.agent.session import Plan, ProposedToolCall, SessionState, ToolResult
from open_keynote_agent.agent.validation import validate_arg_types


def execute_plan(
    plan: Plan,
    registry: ToolRegistry,
    state: SessionState,
    on_step_start: Callable[[int, ProposedToolCall], None] | None = None,
) -> list[ToolResult]:
    """Execute an approved plan step by step.

    on_step_start(step_index, step) is called immediately before each handler,
    so callers can emit a tool_called event before execution begins.
    """
    results: list[ToolResult] = []

    for step_index, step in enumerate(plan.steps):
        tool_def = registry.get(step.tool)
        if tool_def is None:
            result = ToolResult(
                tool=step.tool,
                args=step.args,
                ok=False,
                error=f"Tool not found in registry: {step.tool!r}",
                observation=f"Error: tool {step.tool!r} not found.",
            )
            results.append(result)
            state.context.setdefault("_observations", []).append(result.observation)
            break

        required = tool_def.parameters.get("required", [])
        missing = [r for r in required if r not in step.args]
        if missing:
            result = ToolResult(
                tool=step.tool,
                args=step.args,
                ok=False,
                error=f"Missing required args: {missing}",
                observation=f"Error: {step.tool} missing args {missing}.",
            )
            results.append(result)
            state.context.setdefault("_observations", []).append(result.observation)
            break

        type_errors = validate_arg_types(step.args, tool_def.parameters)
        if type_errors:
            result = ToolResult(
                tool=step.tool,
                args=step.args,
                ok=False,
                error=f"Arg type errors: {type_errors}",
                observation=f"Error: {step.tool} arg type errors: {type_errors}.",
            )
            results.append(result)
            state.context.setdefault("_observations", []).append(result.observation)
            break

        if on_step_start is not None:
            on_step_start(step_index, step)

        try:
            output = tool_def.handler(step.args, state.context)
            observation = output.get("observation", f"{step.tool} completed.")
            result = ToolResult(
                tool=step.tool,
                args=step.args,
                ok=True,
                output=output,
                observation=observation,
            )
        except Exception as exc:
            result = ToolResult(
                tool=step.tool,
                args=step.args,
                ok=False,
                error=str(exc),
                observation=f"Error in {step.tool}: {exc}",
            )
            results.append(result)
            state.context.setdefault("_observations", []).append(result.observation)
            break

        results.append(result)
        state.context.setdefault("_observations", []).append(observation)

    return results
