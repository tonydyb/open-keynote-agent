from __future__ import annotations

from open_keynote_agent.agent.registry import ToolRegistry
from open_keynote_agent.agent.session import Plan, SessionState, ToolResult


def execute_plan(
    plan: Plan,
    registry: ToolRegistry,
    state: SessionState,
) -> list[ToolResult]:
    results: list[ToolResult] = []

    for step in plan.steps:
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
