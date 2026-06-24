# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
uv sync --extra dev              # core + pytest + ruff
uv sync --extra dev --extra bedrock   # add AWS Bedrock
uv sync --extra dev --extra openai    # add OpenAI
uv sync --extra dev --extra gemini    # add Gemini
```

Copy `.env.example` to `.env` and set `OMA_LLM_PROVIDER` to `fake`, `bedrock`, `openai`, or `gemini`.

## Commands

```bash
uv run pytest                           # run all tests
uv run pytest tests/test_filesystem.py  # run a single test file
uv run pytest -k "test_move_files"      # run tests matching a name pattern
uv run ruff check .                     # lint
uv run oma --help                       # CLI help
uv run oma organize <folder> --dry-run
uv run oma organize <folder> --apply
uv run oma ask "organize ~/Downloads into PDFs and Images"
```

All tests run without cloud credentials or API keys — the default `OMA_LLM_PROVIDER=fake` is used.

## Architecture

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
- Every CLI run writes to `.runs/<YYYYMMDDTHHMMSSz>/`: `request.json`, `plan.json`, `tool_calls.jsonl`, `result.json`

### CLI (`cli.py`)
- Two main commands: `organize` (rule-based, no LLM) and `ask` (LLM-driven)
- Both default to dry-run unless `--apply` is passed; `handle_plan()` owns the confirmation prompt
