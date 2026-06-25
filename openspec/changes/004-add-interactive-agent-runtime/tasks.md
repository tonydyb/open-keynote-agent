# Tasks

## 1. Tool Registry

- [ ] Define `ToolDefinition` (name, description, parameters schema, mutating flag, handler).
- [ ] Implement `ToolRegistry` with register and lookup operations.
- [ ] Reject registration of duplicate tool names.
- [ ] Add tests for registration and lookup.

## 2. Demo Tools

- [ ] Implement `demo.create_document` (stores name in session context).
- [ ] Implement `demo.add_slide` (appends slide to session context).
- [ ] Implement `demo.set_text` (updates slide text in session context).
- [ ] Implement `demo.export_pdf` (writes a placeholder file, records path in context).
- [ ] Implement `demo.get_document_info` (returns current context state, non-mutating).
- [ ] Register all demo tools in a `register_demo_tools(registry)` helper.
- [ ] Add tests for each demo tool.

## 3. Session State

- [ ] Define `ProposedToolCall` (tool, args, description).
- [ ] Define `Plan` (steps: list of ProposedToolCall).
- [ ] Define `ToolResult` (tool, args, ok, output, error, observation).
- [ ] Define `Turn` (instruction, plan, approved, results, observations).
- [ ] Define `SessionState` (session_id, turns, context).
- [ ] Add tests for session state mutation.

## 4. Planner

- [ ] Implement `plan_turn(instruction, state, registry, llm_client) -> Plan`.
- [ ] Build tool description list from registry for the LLM prompt.
- [ ] Include recent observations from session state in the prompt.
- [ ] Validate proposed tool names against the registry before returning.
- [ ] Reject plans with missing required parameters.
- [ ] Add tests using `FakeLLMClient` for valid and invalid plans.

## 5. Executor

- [ ] Implement `execute_plan(plan, registry, state) -> list[ToolResult]`.
- [ ] Validate tool arguments against the parameter schema before calling.
- [ ] Record result or error as a `ToolResult`.
- [ ] Append human-readable observations to session state.
- [ ] Stop on first tool error and record it; do not silently continue.
- [ ] Add tests for successful execution, argument validation error, and handler exception.

## 6. Session Event Log

- [ ] Define `SessionEvent` (seq, type, ts, payload).
- [ ] Define event types: `turn_start`, `plan_proposed`, `plan_approved`, `plan_rejected`, `tool_called`, `tool_result`, `session_end`.
- [ ] Implement event log writer that appends NDJSON to `.runs/<session-id>/events.jsonl`.
- [ ] Ensure each event has a monotonically increasing sequence number.
- [ ] Add tests for event ordering and serialization.

## 7. CLI Session Command

- [ ] Add `oka session` command to `cli.py`.
- [ ] Start a session, display the `oma>` prompt, and read input line by line.
- [ ] Call planner, display the proposed plan, and prompt `Apply? [y/N]`.
- [ ] Call executor on approval; skip on rejection.
- [ ] Display observations after execution.
- [ ] Log all events to the session event log.
- [ ] Exit cleanly on `done`, `exit`, `quit`, and EOF.
- [ ] Add `--no-confirm` flag for non-interactive scripting and tests.

## 8. Integration Test

- [ ] Write an end-to-end test: run a session turn using `FakeLLMClient` and demo tools.
- [ ] Verify session state contains the correct turn and observations.
- [ ] Verify the event log contains the correct sequence of events.
- [ ] Confirm no test requires cloud credentials or API keys.

## 9. Quality Bar

- [ ] Run `ruff check`.
- [ ] Run `pytest`.
- [ ] Verify `oka organize` and `oka ask` still work without modification.
- [ ] Verify no tests require cloud credentials or API keys.
- [ ] Verify all mutating demo tool calls require confirmation in the CLI.
