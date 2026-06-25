# Open Keynote Agent

An open-source macOS agent for creating and editing Apple Keynote presentations through natural-language, step-by-step workflows.

Project slug: `open-keynote-agent`.

Note: the current Python package and CLI still use the earlier `open_keynote_agent` / `oka` names until a later mechanical rename.

## Current Milestone

The current implementation is a CLI file organizer. It is the first learning milestone for the agent foundation:

- LLM provider abstraction
- structured request validation
- deterministic local tools
- confirmation before mutation
- run logs
- tests without cloud credentials

Future work is focused on Keynote-specific agent workflows.

## Quickstart

1. Sync dependencies and install the package:

```bash
uv sync
```

2. View the CLI help:

```bash
uv run oka --help
```

3. Run the version command:

```bash
uv run oka version
```

4. Preview deterministic file organization:

```bash
uv run oka organize ./demo --dry-run
```

5. Preview natural-language file organization:

```bash
uv run oka ask "Organize ./demo into PDFs and Images"
```

This command requires `OMA_LLM_PROVIDER` to be set to `bedrock`, `openai`, or `gemini`. The `fake` provider is only for tests.

6. Apply a natural-language plan after confirmation:

```bash
uv run oka ask "Organize ./demo into PDFs and Images" --apply
```

## Environment

Copy `.env.example` to `.env` and configure your preferred LLM provider when ready.

For example, using OpenAI:

```bash
OMA_LLM_PROVIDER=openai
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=gpt-4o
```

## LLM Provider Setup

Set `OMA_LLM_PROVIDER` to one of:

- `fake` for local testing
- `bedrock` for AWS Bedrock
- `openai` for OpenAI API
- `gemini` for Gemini API

Configure provider environment variables:

- Bedrock: `AWS_PROFILE`, `AWS_REGION`, `BEDROCK_MODEL_ID`
- OpenAI: `OPENAI_API_KEY`, optional `OPENAI_MODEL`
- Gemini: `GEMINI_API_KEY`, optional `GEMINI_MODEL`

The CLI uses `load_llm_client_from_env()` to select the provider without leaking provider logic into the organizer.

Natural-language requests default to dry-run. File moves only happen when apply mode is requested and the confirmation prompt is accepted.

## Safety Notes

- `oka organize` and `oka ask` default to previewing the move plan without changing files.
- `--apply` still requires an explicit confirmation prompt before any file is moved.
- Existing destination files are never overwritten; conflicting moves are skipped and recorded.
- File operations are limited to regular files inside the target directory.
- Tests use `FakeLLMClient` and do not require cloud credentials, API keys, or network access.
- Each run writes audit artifacts under `.runs/<run-id>/`.

## Keynote Roadmap

The next project direction is an interactive Keynote agent:

1. Add an interactive agent runtime with session state, planner, executor, tool registry, observations, and step-by-step logs.
2. Add Keynote tools using AppleScript or JXA for creating documents, adding slides, editing text, inserting images, and exporting PDF.
3. Add verification for generated `.key` and PDF outputs.
4. Expose session events through an API suitable for a future Studio UI.
