# Tasks

## 1. Tool Registry

- [x] Define `ToolDefinition` (name, description, parameters schema, mutating flag, handler).
- [x] Implement `ToolRegistry` with register and lookup operations.
- [x] Reject registration of duplicate tool names.
- [x] Add tests for registration and lookup.

## 2. Demo Tools

- [x] Implement `demo.create_document` (stores name in session context).
- [x] Implement `demo.add_slide` (appends slide to session context).
- [x] Implement `demo.set_text` (updates slide text in session context).
- [x] Implement `demo.export_pdf` (writes a placeholder file, records path in context).
- [x] Implement `demo.get_document_info` (returns current context state, non-mutating).
- [x] Register all demo tools in a `register_demo_tools(registry)` helper.
- [x] Add tests for each demo tool.

## 3. Session State

- [x] Define `ProposedToolCall` (tool, args, description).
- [x] Define `Plan` (steps: list of ProposedToolCall).
- [x] Define `ToolResult` (tool, args, ok, output, error, observation).
- [x] Define `Turn` (instruction, plan, approved, results, observations).
- [x] Define `SessionState` (session_id, turns, context).
- [x] Add tests for session state mutation.

## 4. Planner

- [x] Implement `plan_turn(instruction, state, registry, llm_client) -> Plan`.
- [x] Build tool description list from registry for the LLM prompt.
- [x] Include recent observations from session state in the prompt.
- [x] Validate proposed tool names against the registry before returning.
- [x] Reject plans with missing required parameters.
- [x] Add tests using `FakeLLMClient` for valid and invalid plans.

## 5. Executor

- [x] Implement `execute_plan(plan, registry, state) -> list[ToolResult]`.
- [x] Validate tool arguments against the parameter schema before calling.
- [x] Record result or error as a `ToolResult`.
- [x] Append human-readable observations to session state.
- [x] Stop on first tool error and record it; do not silently continue.
- [x] Add tests for successful execution, argument validation error, and handler exception.

## 6. Session Event Log

- [x] Define `SessionEvent` (seq, type, ts, payload).
- [x] Define event types: `turn_start`, `plan_proposed`, `plan_approved`, `plan_rejected`, `tool_called`, `tool_result`, `session_end`.
- [x] Implement event log writer that appends NDJSON to `.runs/<session-id>/events.jsonl`.
- [x] Ensure each event has a monotonically increasing sequence number.
- [x] Add tests for event ordering and serialization.

## 7. CLI Session Command

- [x] Add `oka session` command to `cli.py`.
- [x] Start a session, display the `oka>` prompt, and read input line by line.
- [x] Call planner, display the proposed plan, and prompt `Apply? [y/N]`.
- [x] Call executor on approval; skip on rejection.
- [x] Display observations after execution.
- [x] Log all events to the session event log.
- [x] Exit cleanly on `done`, `exit`, `quit`, and EOF.
- [x] Add `--no-confirm` flag for non-interactive scripting and tests.

## 8. Integration Test

- [x] Write an end-to-end test: run a session turn using `FakeLLMClient` and demo tools.
- [x] Verify session state contains the correct turn and observations.
- [x] Verify the event log contains the correct sequence of events.
- [x] Confirm no test requires cloud credentials or API keys.

## 9. Quality Bar

- [x] Run `ruff check`.
- [x] Run `pytest`.
- [x] Verify `oka organize` and `oka ask` still work without modification.
- [x] Verify no tests require cloud credentials or API keys.
- [x] Verify all mutating demo tool calls require confirmation in the CLI.
