# 001-add-cli-file-organizer

## Summary

Add the first usable CLI workflow for `open-mac-agent`: a file organization agent that can understand a natural-language request, inspect a local folder, propose a safe move plan, ask for confirmation, execute approved moves, and write an auditable run log.

## Motivation

The project needs a small but real agent loop before adding macOS desktop automation. Organizing a folder is a good first task because it exercises the core agent shape without requiring fragile GUI control:

- Parse user intent.
- Convert intent into a structured plan.
- Call deterministic local tools.
- Show a dry-run preview.
- Require confirmation for filesystem changes.
- Execute and report results.
- Capture enough runtime state for debugging and replay.

This creates a reusable foundation for later macOS app adapters.

## Goals

- Provide a Python CLI entrypoint named `oma`.
- Support deterministic folder organization by file type.
- Support natural-language organization requests through a selectable LLM provider: AWS Bedrock, OpenAI API, or Gemini API.
- Ensure destructive or mutating operations require explicit confirmation.
- Ensure dry-run mode is available and is the default for natural-language requests.
- Avoid overwriting files by default.
- Persist run artifacts for every agent execution.
- Include tests for classification, planning, conflict handling, and dry-run behavior.

## Non-Goals

- Do not implement macOS GUI automation in this change.
- Do not implement recursive multi-step autonomous workflows beyond file organization.
- Do not support remote storage providers.
- Do not delete files.
- Do not overwrite existing files unless a future spec explicitly adds that behavior.
- Do not require real LLM provider calls in automated tests.

## User Stories

- As a learner, I can run `oma organize ./demo --dry-run` and see where files would be moved.
- As a learner, I can run `oma organize ./demo --apply` and approve a safe move plan.
- As a user, I can ask `oma ask "帮我整理 ./demo，把 PDF、图片、文档分类"` and receive a structured plan.
- As a developer, I can inspect `.runs/<run-id>/` to understand what the agent planned and executed.
- As a developer, I can run tests without cloud credentials or API keys by using a fake LLM client.

## Risks

- Filesystem mutation can cause data loss if confirmation and conflict handling are weak.
- LLM output may be malformed or unsafe.
- Model IDs and credentials vary across Bedrock, OpenAI, and Gemini.
- File classification by extension is imperfect.

## Mitigations

- Default to dry-run for natural-language commands.
- Never overwrite destination files.
- Validate all LLM output with typed schemas.
- Keep all filesystem mutation inside deterministic tools.
- Add a fake LLM implementation for tests.
- Make provider selection, credentials, region, and model IDs configurable.

## Success Criteria

- `oma organize <folder> --dry-run` produces a readable move preview.
- `oma organize <folder> --apply` asks for confirmation before moving files.
- `oma ask "<natural language request>"` can plan a folder organization task using the configured LLM provider.
- Tests pass without network access, AWS credentials, or API keys.
- Each run writes request, plan, tool-call, and result artifacts under `.runs/`.
