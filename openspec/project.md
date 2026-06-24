# open-mac-agent

## Purpose

`open-mac-agent` is an open-source learning project for building a macOS-first AI agent. The first phase focuses on a CLI agent that can safely plan and execute local file organization tasks.

## Principles

- Prefer deterministic local tools for execution.
- Use LLMs for intent parsing, planning, and explanation, not for unchecked system mutation.
- Require explicit confirmation before moving, deleting, overwriting, or sending data.
- Support dry-run mode for every mutating workflow.
- Record each run with enough detail to debug, replay, and audit agent behavior.
- Keep provider-specific model integrations behind narrow adapters.

## Initial Scope

- Python CLI package.
- Folder organization workflow.
- Pluggable LLM adapters for AWS Bedrock, OpenAI API, and Gemini API.
- Local filesystem tools.
- Execution logs and tests.

## Out of Scope for Phase 1

- macOS GUI automation.
- Accessibility API integration.
- Long-running autonomous background agents.
- Browser control.
- Remote file operations.
