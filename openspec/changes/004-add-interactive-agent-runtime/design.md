# Design: Interactive Agent Runtime

## Overview

This change introduces a multi-turn agent session runtime. The CLI is one renderer of a runtime that produces structured events. Future changes can add an SSE endpoint, a Studio UI, or Keynote tools by extending the registry — not by modifying the core runtime.

The data flow per turn is:

```text
user instruction
  -> planner (LLM + tool registry)
  -> proposed tool calls
  -> confirmation prompt
  -> executor (tool registry)
  -> tool results
  -> observations added to session state
  -> event appended to session log
```

## Package Layout

New modules added under `src/open_keynote_agent/`:

```text
agent/
  session.py       # SessionState, session lifecycle
  planner.py       # Plan, ProposedToolCall, plan_turn()
  executor.py      # execute_plan(), ToolResult
  registry.py      # ToolRegistry, ToolDefinition

runtime/
  events.py        # SessionEvent, event types (updated)
  session.py       # run log writing (existing, extended)

tools/
  demo.py          # DemoTools: create_document, add_slide, export_pdf
```

The existing `organizer.py`, `filesystem.py`, `cli.py`, `llm/`, and `runtime/session.py` are not modified by this change.

## Session State

`SessionState` holds all mutable context for one `oka session` run:

```text
SessionState:
  session_id: str
  turns: list[Turn]
  context: dict            # arbitrary key/value set by tools
```

Each `Turn` records one user instruction and its outcome:

```text
Turn:
  instruction: str
  plan: Plan
  approved: bool
  results: list[ToolResult]
  observations: list[str]
```

Session state is in-memory. The event log on disk is the durable record.

## Planner

`plan_turn(instruction, state, registry, llm_client) -> Plan`

The planner calls the LLM with:
- The current instruction.
- A description of all registered tools (name, description, parameters).
- Recent observations from prior turns (up to a configurable window).

The LLM returns a list of proposed tool calls. The planner validates each proposed call against the registry before returning the plan. Invalid tool names or missing required parameters are rejected before the user is shown a plan.

```text
Plan:
  steps: list[ProposedToolCall]

ProposedToolCall:
  tool: str           # registry key, e.g. "demo.create_document"
  args: dict
  description: str    # human-readable summary shown to the user
```

## Tool Registry

`ToolRegistry` is a simple mapping from name to `ToolDefinition`.

```text
ToolDefinition:
  name: str
  description: str
  parameters: dict          # JSON Schema
  mutating: bool            # true = requires confirmation
  handler: Callable
```

Tools register at startup. The registry is passed to both the planner and the executor. The CLI does not hard-code tool names.

## Executor

`execute_plan(plan, registry, session_state) -> list[ToolResult]`

The executor calls each tool in the plan in sequence. It:
- Looks up the handler in the registry.
- Validates arguments against the tool's parameter schema.
- Calls the handler.
- Records the result or error as a `ToolResult`.
- Adds a human-readable observation to session state.

```text
ToolResult:
  tool: str
  args: dict
  ok: bool
  output: dict
  error: str | None
  observation: str
```

If a tool raises an exception, the executor records the error and stops the current plan. It does not silently continue.

## Event Log

Every action in a session is appended to `.runs/<session-id>/events.jsonl` as a newline-delimited JSON event:

```text
SessionEvent:
  seq: int
  type: str          # "turn_start" | "plan_proposed" | "plan_approved" | "plan_rejected" |
                     #  "tool_called" | "tool_result" | "session_end"
  ts: str            # ISO 8601 UTC
  payload: dict
```

The event log is the authoritative record of what happened. It is designed to be replayed and is compatible with SSE delivery (`data: <json>\n\n`) for a future frontend.

## Demo Tools

Demo tools are fake implementations that simulate a Keynote-like workflow without requiring Keynote or AppleScript. They accept the same parameters that real Keynote tools will use.

| Tool name | Parameters | Mutating |
|---|---|---|
| `demo.create_document` | `name: str` | yes |
| `demo.add_slide` | `kind: str`, `title: str` | yes |
| `demo.set_text` | `slide: int`, `text: str` | yes |
| `demo.export_pdf` | `path: str \| None` | yes |
| `demo.get_document_info` | _(none)_ | no |

Demo tools store state in the `SessionState.context` dict. They return realistic structured output so executor and planner logic can be tested end-to-end.

## CLI Command

```bash
uv run oka session
```

Starts an interactive REPL. Each turn:

1. Prints the `oka>` prompt.
2. Reads a line of input.
3. Calls the planner.
4. Displays the proposed plan.
5. Prompts `Apply? [y/N]`.
6. If approved, calls the executor and displays observations.
7. If rejected, skips execution.
8. Logs the event regardless.

The REPL exits on `done`, `exit`, `quit`, or EOF. A `--no-confirm` flag bypasses the confirmation prompt; it is intended only for scripting and tests.

## Safety

- All tool calls with `mutating=True` require explicit per-step approval from the user.
- The executor validates arguments before calling any handler.
- The planner rejects unrecognized tool names before showing a plan to the user.
- Demo tools never touch the filesystem except for `demo.export_pdf`, which writes to a temp path by default.

## Testing Strategy

Unit tests:
- `plan_turn()` with `FakeLLMClient` returns a valid plan for known instructions.
- Planner rejects unknown tool names.
- Executor calls the handler and records results.
- Executor records an error without crashing on handler exception.
- Session state accumulates turns and observations correctly.
- Event log entries have correct types and sequences.

Integration test:
- Run a full session turn (plan → approve → execute) using demo tools and `FakeLLMClient`.
- Verify the event log contains the expected sequence.

No test requires cloud credentials, API keys, or Keynote.
