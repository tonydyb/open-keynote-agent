# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project

**Open Keynote Agent** — an open-source macOS agent for creating and editing Apple Keynote presentations through natural-language, step-by-step workflows.

Project slug: `open-keynote-agent`. Python package: `open_keynote_agent`. CLI command: `oka`.

## Current State

The existing implementation is a **CLI file organizer** — the completed first learning milestone. It established the agent foundation:

- LLM provider abstraction (Bedrock, OpenAI, Gemini, Fake)
- Structured request validation (Pydantic)
- Deterministic local tools
- Confirmation before mutation
- Run logs
- Tests without cloud credentials

This milestone is not the long-term product focus. Future work is Keynote-specific.

## Future Direction

Next changes should build toward an interactive Keynote agent:

- Interactive agent runtime with session state, planner, executor, tool registry, and observations
- Keynote adapter using AppleScript or JXA first, Accessibility API fallback later
- Export to PDF and basic verification
- Session event stream suitable for a future Studio UI

## Setup

```bash
uv sync --all-extras                  # all providers + dev tools (recommended)
uv sync --extra dev              # core + pytest + ruff only
uv sync --extra dev --extra bedrock   # add AWS Bedrock
uv sync --extra dev --extra openai    # add OpenAI
uv sync --extra dev --extra gemini    # add Gemini
```

When using a single provider extra, keep `--extra dev` included so pytest and ruff remain installed.

Copy `.env.example` to `.env` and set `OMA_LLM_PROVIDER` to `fake`, `bedrock`, `openai`, or `gemini`.

## Commands

```bash
uv run pytest                           # run all tests (no Keynote required)
uv run pytest tests/test_filesystem.py  # run a single test file
uv run pytest -k "test_move_files"      # run tests matching a name pattern
uv run ruff check .                     # lint
uv run oka --help                       # CLI help
uv run oka organize <folder> --dry-run
uv run oka organize <folder> --apply
uv run oka ask "organize ~/Downloads into PDFs and Images"
uv run oka session                      # interactive session with demo tools
uv run oka session --tools demo         # same as default
uv run oka session --tools keynote      # real Keynote via AppleScript (macOS only)
RUN_KEYNOTE_INTEGRATION=1 uv run python -m pytest -m keynote_integration  # Keynote smoke test
```

All tests run without cloud credentials or API keys — the default `OMA_LLM_PROVIDER=fake` is used.

Unit tests do not require Keynote, `osascript`, macOS GUI access, or special permissions. The `keynote_integration` marker gates tests that call real Keynote; they are skipped unless `RUN_KEYNOTE_INTEGRATION=1` is set.

When running `oka session --tools keynote`, macOS may prompt for permission to control Keynote via Automation. Grant it when asked.

## Architecture (File Organizer Milestone)

The data flow is: **CLI → organizer (plan) → filesystem (execute) → session (log)**

### Core data models (`organizer.py`)
- `OrganizePlan` — the central value passed between layers, contains `operations: list[MoveOperation]` and `skipped: list[SkippedFile]`
- `build_organize_plan(target_dir, categories=None)` — pure function, no I/O side effects, safe to call repeatedly

### Execution boundary (`filesystem.py`)
- `move_files(plan)` — the **only** function that mutates the filesystem; re-validates paths inside `target_dir` and skips rather than overwriting

### LLM layer (`llm/`)
- `LLMClient` is a `Protocol` with a single method `complete_json(messages, schema) -> dict`
- `parser.py::load_llm_client_from_env()` selects the provider via `OMA_LLM_PROVIDER`
- `parser.py::parse_natural_language_request()` calls the LLM and validates output through `LLMPlanResponse` (Pydantic) — the result feeds `target_dir` and `categories` into `build_organize_plan`
- `FakeLLMClient` is used in all tests; inject `FakeLLMClient(response={...})` to control LLM output

### Runtime logging (`runtime/session.py`)
- Every CLI run writes to `.runs/<YYYYMMDDTHHMMSSZ>/`: `request.json`, `plan.json`, `tool_calls.jsonl`, `result.json`

### CLI (`cli.py`)
- Two main commands: `organize` (rule-based, no LLM) and `ask` (LLM-driven)
- Both default to dry-run unless `--apply` is passed; `handle_plan()` owns the confirmation prompt
