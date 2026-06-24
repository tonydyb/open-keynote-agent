# open-mac-agent

A macOS-first AI agent CLI for local file organization.

## Quickstart

1. Sync dependencies and install the package:

```bash
uv sync
```

2. View the CLI help:

```bash
uv run oma --help
```

3. Run the version command:

```bash
uv run oma version
```

4. Preview deterministic file organization:

```bash
uv run oma organize ./demo --dry-run
```

5. Preview natural-language file organization:

```bash
uv run oma ask "Organize ./demo into PDFs and Images"
```

6. Apply a natural-language plan after confirmation:

```bash
uv run oma ask "Organize ./demo into PDFs and Images" --apply
```

## Environment

Copy `.env.example` to `.env` and configure your preferred LLM provider when ready.

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

- `oma organize` and `oma ask` default to previewing the move plan without changing files.
- `--apply` still requires an explicit confirmation prompt before any file is moved.
- Existing destination files are never overwritten; conflicting moves are skipped and recorded.
- File operations are limited to regular files inside the target directory.
- Tests use `FakeLLMClient` and do not require cloud credentials, API keys, or network access.
- Each run writes audit artifacts under `.runs/<run-id>/`.
