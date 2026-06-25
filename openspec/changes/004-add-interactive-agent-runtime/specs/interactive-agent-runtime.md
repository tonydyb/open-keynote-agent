# Spec: Interactive Agent Runtime

## Purpose

This spec defines the interactive agent runtime for `open-keynote-agent`. The runtime supports multi-turn CLI sessions where the user issues natural-language instructions, the agent proposes tool calls, the user approves or rejects them, and results are recorded.

The runtime is designed so the CLI is one renderer. The core runtime emits structured events that can later be consumed by an SSE stream or a Studio UI frontend without modifying the runtime.

## Session Lifecycle

1. User runs `oka session`.
2. A `SessionState` is created with a unique `session_id`.
3. The session event log is opened at `.runs/<session-id>/events.jsonl`.
4. The REPL loop begins:
   a. Display `oka>` prompt and read one line of input.
   b. If input is `done`, `exit`, `quit`, or EOF: emit `session_end` event and exit.
   c. Emit `turn_start` event.
   d. Call `plan_turn()` with the instruction, current state, tool registry, and LLM client.
   e. Emit `plan_proposed` event.
   f. Display the plan and prompt `Apply? [y/N]`.
   g. If approved: emit `plan_approved`, call `execute_plan()`, emit `tool_called` and `tool_result` for each step, display observations.
   h. If rejected: emit `plan_rejected`.
   i. Append the turn to session state.
5. Session ends.

## SessionState

```text
SessionState
  session_id: str           # unique per session, used as the run directory name
  turns: list[Turn]         # ordered list of completed turns
  context: dict             # key/value state shared between tools within one session
```

```text
Turn
  instruction: str          # raw user input
  plan: Plan                # proposed plan from the planner
  approved: bool            # whether the user approved execution
  results: list[ToolResult] # one entry per executed tool call
  observations: list[str]   # human-readable summaries appended to state
```

## Planner

Input: user instruction, session state, tool registry, LLM client.

Output: `Plan` with a list of `ProposedToolCall` entries.

```text
Plan
  steps: list[ProposedToolCall]

ProposedToolCall
  tool: str           # registered tool name, e.g. "demo.create_document"
  args: dict          # key/value arguments
  description: str    # human-readable summary for the confirmation prompt
```

The planner sends the LLM:
- A system prompt describing the tool registry (tool names, descriptions, parameters).
- The instruction.
- Recent observations from prior turns (sliding window, configurable).

The LLM returns a JSON structure matching a `Plan` schema. The planner validates:
- Each tool name exists in the registry.
- Required parameters are present.

If validation fails, the planner raises a `PlanValidationError` before showing anything to the user.

## Tool Registry

```text
ToolDefinition
  name: str           # unique key, e.g. "demo.create_document"
  description: str    # shown to the LLM and the user
  parameters: dict    # JSON Schema for args validation
  mutating: bool      # if true, requires confirmation before execution
  handler: Callable   # (args: dict, context: dict) -> dict
```

`ToolRegistry` is a flat dict keyed by `name`. Tools are registered at startup. The planner and executor are both passed the same registry instance.

## Executor

Input: approved plan, tool registry, session state.

Output: `list[ToolResult]`.

```text
ToolResult
  tool: str
  args: dict
  ok: bool
  output: dict        # returned by the handler on success
  error: str | None   # error message on failure
  observation: str    # appended to session state
```

Execution is sequential. On handler exception or argument validation failure, the executor records the error as a `ToolResult` with `ok=False` and stops. It does not continue to subsequent steps after a failure.

Tool handlers receive `(args, context)` and return a plain dict. They may mutate `context` in place to share state across tools within one session.

## Session Events

Events are appended to `.runs/<session-id>/events.jsonl` as newline-delimited JSON.

```text
SessionEvent
  seq: int            # monotonically increasing from 0
  type: str           # see event types below
  ts: str             # ISO 8601 UTC timestamp
  payload: dict       # event-specific fields
```

Event types:

| type | payload fields |
|---|---|
| `session_start` | `session_id` |
| `turn_start` | `turn_index`, `instruction` |
| `plan_proposed` | `turn_index`, `steps: [{tool, args, description}]` |
| `plan_approved` | `turn_index` |
| `plan_rejected` | `turn_index` |
| `tool_called` | `turn_index`, `step_index`, `tool`, `args` |
| `tool_result` | `turn_index`, `step_index`, `ok`, `output`, `error`, `observation` |
| `session_end` | `session_id`, `turn_count` |

The event log is the authoritative record of the session. It is structured for SSE compatibility: each event can be emitted as `data: <json>\n\n` without modification.

## Demo Tools

Demo tools simulate a Keynote-like workflow. They store state in `SessionState.context` under the key `"demo"`.

| Tool | Parameters | Mutating | Behavior |
|---|---|---|---|
| `demo.create_document` | `name: str` | yes | Initializes `context["demo"]` with document name and empty slides list. |
| `demo.add_slide` | `kind: str`, `title: str` | yes | Appends a slide dict to `context["demo"]["slides"]`. |
| `demo.set_text` | `slide: int`, `text: str` | yes | Updates the text field of the specified slide (1-indexed). |
| `demo.export_pdf` | `path: str \| None` | yes | Writes a placeholder `.pdf` file; defaults to `<name>.pdf` in the current directory. |
| `demo.get_document_info` | _(none)_ | no | Returns current document name and slide count from context. |

Demo tools should fail with a clear error if called before `demo.create_document` (except `demo.get_document_info`, which returns an empty state).

## Confirmation Requirement

Any tool with `mutating=True` must display a confirmation prompt and receive `y` or `yes` (case-insensitive) before execution. The default answer is no. The `--no-confirm` flag bypasses this check; it is intended only for tests and non-interactive scripting.

## CLI User Flow

```text
$ uv run oka session

oka> create a keynote deck named demo
assistant> Plan:
  1. demo.create_document name=demo
Apply? [y/N] y
> Created document "demo" with 0 slides.

oka> add a title slide called Open Keynote Agent
assistant> Plan:
  1. demo.add_slide kind=title title="Open Keynote Agent"
Apply? [y/N] y
> Added slide 1: title "Open Keynote Agent".

oka> export it as PDF
assistant> Plan:
  1. demo.export_pdf
Apply? [y/N] y
> Exported to demo.pdf.

oka> done
```

## Future Compatibility

The runtime is designed for extension:

- **New tools**: register a `ToolDefinition` and call `register()` at startup. No core runtime changes needed.
- **Keynote tools**: implement handlers that call AppleScript or JXA; register under the `keynote.*` namespace.
- **SSE / Studio UI**: consume `events.jsonl` or emit events from the executor directly over an HTTP stream. The event schema is stable.
- **API server**: wrap the planner and executor in an HTTP handler; session state moves to a persistent store. The CLI REPL becomes one client.

## Out of Scope

- Real Keynote automation (AppleScript, JXA, Accessibility API).
- Autonomous multi-step loops without per-step approval.
- HTTP server or SSE endpoint.
- Package, CLI command, or repository renaming.
