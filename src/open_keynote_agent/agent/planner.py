from __future__ import annotations

import json
from typing import Any

from open_keynote_agent.agent.registry import ToolRegistry
from open_keynote_agent.agent.session import Plan, ProposedToolCall, SessionState
from open_keynote_agent.agent.validation import validate_arg_types
from open_keynote_agent.llm.base import LLMClient


class PlanValidationError(ValueError):
    pass


def _registry_description(registry: ToolRegistry) -> str:
    lines = []
    for tool in registry.all():
        params = json.dumps(tool.parameters.get("properties", {}))
        lines.append(f"- {tool.name}: {tool.description} | params: {params}")
    return "\n".join(lines)


def _build_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "tool": {"type": "string"},
                        "args": {"type": "object"},
                        "description": {"type": "string"},
                    },
                    "required": ["tool", "description"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["steps"],
        "additionalProperties": False,
    }


def plan_turn(
    instruction: str,
    state: SessionState,
    registry: ToolRegistry,
    llm_client: LLMClient,
) -> Plan:
    tools_desc = _registry_description(registry)
    recent = state.recent_observations()
    context_block = ""
    if recent:
        context_block = "\nRecent observations:\n" + "\n".join(f"- {o}" for o in recent)

    system = (
        "You are a planning assistant. Given a user instruction and a list of available tools, "
        "return a JSON plan with the steps needed to fulfil the instruction. "
        "Only use tools from the provided list. Return only valid JSON.\n\n"
        f"Available tools:\n{tools_desc}"
        f"{context_block}"
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": instruction},
    ]

    raw = llm_client.complete_json(messages, _build_schema())

    steps_raw = raw.get("steps", [])
    if not isinstance(steps_raw, list):
        raise PlanValidationError("LLM plan 'steps' must be a list")

    steps: list[ProposedToolCall] = []
    for i, step in enumerate(steps_raw):
        if not isinstance(step, dict):
            raise PlanValidationError(f"Step {i} must be an object")
        tool_name = step.get("tool", "")
        if tool_name not in registry:
            raise PlanValidationError(f"Unknown tool: {tool_name!r}")
        tool_def = registry.get(tool_name)
        assert tool_def is not None
        args = step.get("args", {})
        if not isinstance(args, dict):
            raise PlanValidationError(f"Step {i} args must be an object")
        required = tool_def.parameters.get("required", [])
        missing = [r for r in required if r not in args]
        if missing:
            raise PlanValidationError(
                f"Tool {tool_name!r} missing required args: {missing}"
            )
        type_errors = validate_arg_types(args, tool_def.parameters)
        if type_errors:
            raise PlanValidationError(
                f"Tool {tool_name!r} arg type errors: {type_errors}"
            )
        steps.append(
            ProposedToolCall(
                tool=tool_name,
                args=args,
                description=step.get("description", tool_name),
            )
        )

    return Plan(steps=steps)
