# Open Keynote Agent

## Purpose

`Open Keynote Agent` is an open-source learning project for building a macOS agent focused on creating, editing, verifying, and exporting Apple Keynote presentations through natural-language instructions.

The project slug is `open-keynote-agent`. The Python package is `open_keynote_agent` and the CLI command is `oka`.

## Principles

- Prefer deterministic local tools for execution.
- Use LLMs for intent parsing, planning, and explanation, not for unchecked system mutation.
- Require explicit confirmation before moving, deleting, overwriting, or sending data.
- Support dry-run mode for every mutating workflow.
- Record each run with enough detail to debug, replay, and audit agent behavior.
- Keep provider-specific model integrations behind narrow adapters.
- Treat the user as the final approver for mutating Keynote and filesystem actions.

## Current Milestone

The completed first milestone is a CLI file organizer. It exists to establish the agent foundation:

- Python CLI package.
- LLM provider abstraction for AWS Bedrock, OpenAI API, Gemini API, and fake tests.
- Structured request validation.
- Deterministic local tools.
- Confirmation before mutation.
- Run logs and tests without cloud credentials.

This milestone is not the long-term product focus.

## Future Scope

Future changes should focus on a step-by-step Keynote agent:

- Interactive agent sessions.
- Planner / executor / tool registry.
- Session state and observations.
- Keynote adapter using AppleScript or JXA first.
- Accessibility API fallback later if needed.
- Export to PDF and basic verification.
- Event stream suitable for a future Studio UI.

## Out of Scope for the Next Positioning Change

- Long-running autonomous background agents.
- General-purpose macOS automation across many apps.
- Browser control or remote desktop control.
- Keynote automation implementation details.
