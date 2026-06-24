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
