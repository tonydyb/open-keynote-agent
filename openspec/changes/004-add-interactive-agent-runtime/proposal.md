# Proposal: Add Interactive Agent Runtime

## Summary

Add an interactive CLI agent session runtime to `open-keynote-agent`. The runtime introduces session state, a planner, an executor, a tool registry, tool calls, tool results, and observations. The session produces a structured event log suitable for future use by a Studio UI or SSE stream.

This milestone does not add real Keynote automation. It establishes the runtime that future Keynote tools will plug into.

## Motivation

The existing `oka organize` and `oka ask` commands handle a single one-shot request and exit. They cannot support the step-by-step conversational workflow that a Keynote agent requires:

```text
user> Create a new presentation named demo.
agent> Plan: demo.create_document name=demo — Apply? [y/N]

user> Add a title slide called Open Keynote Agent.
agent> Plan: demo.add_slide kind=title title="Open Keynote Agent" — Apply? [y/N]

user> Export it as PDF.
agent> Plan: demo.export_pdf — Apply? [y/N]
agent> Exported to demo.pdf.
```

To support this, the agent needs:

- A running session that persists context across turns.
- A planner that proposes tool calls for each instruction.
- An executor that runs approved tool calls and records results.
- A tool registry that supplies tools without hardcoding them in the CLI.
- An event model that decouples the runtime from the CLI renderer.

Without this runtime, adding Keynote tools would require rewriting the CLI from scratch. Adding the runtime first keeps later milestones incremental.

## Goals

- Add an `oka session` interactive REPL command.
- Add session state that persists across turns: prior instructions, tool calls, and observations.
- Add a planner that converts user instructions into a list of proposed tool calls.
- Add an executor that runs approved tool calls and records results as observations.
- Add a tool registry that tools can register with at startup.
- Add a structured event log per session.
- Ship fake/demo tools (`demo.*`) so the runtime can be exercised without Keynote.
- Design the runtime so the CLI is only one possible renderer; events can be consumed by a future SSE endpoint or Studio UI.
- Require explicit confirmation before any mutating tool call.

## Non-Goals

- Do not implement Keynote automation in this change.
- Do not add AppleScript, JXA, or Accessibility API calls.
- Do not rename the Python package, CLI command, or repository directory.
- Do not implement an HTTP server or SSE endpoint in this change.
- Do not add autonomous multi-step agent loops that act without per-step approval.
- Do not remove or modify the existing `oka organize` and `oka ask` commands.

## User Stories

- As a developer, I can run `oka session` and interact with the agent turn by turn.
- As a developer, I can issue instructions in natural language and receive a proposed plan before anything executes.
- As a developer, I can approve or reject a plan before mutating state.
- As a developer, I can inspect `.runs/<session-id>/events.jsonl` to replay exactly what happened.
- As a developer, I can write a new tool, register it, and have it appear in the planner and executor without modifying core runtime code.
- As a developer, I can run all session runtime tests without cloud credentials or API keys.

## Risks

- The LLM may propose the wrong tool or incorrect arguments.
- Session state may grow unbounded for very long sessions.
- Fake tools that succeed unconditionally may mask executor bugs.

## Mitigations

- Validate all tool calls against the tool registry before executing.
- Keep session state bounded; summarize or truncate if needed in a later change.
- Fake tools should return realistic structured results, not trivial stubs.
- All mutating calls require explicit per-step approval.

## Success Criteria

- `oka session` launches an interactive REPL.
- Each user instruction produces a plan with at least one proposed tool call.
- The user can accept or reject the plan before execution.
- Accepted tool calls run, and their results are added to session state as observations.
- Each session writes a complete event log to `.runs/<session-id>/`.
- Tests pass using `FakeLLMClient` and demo tools, without any cloud credentials or API keys.
