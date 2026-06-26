# Open Keynote Agent

An open-source macOS agent for creating and editing Apple Keynote presentations through natural-language, step-by-step workflows.

Project slug: `open-keynote-agent`.

Python package: `open_keynote_agent`. CLI command: `oka`.

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

## Keynote Adapter

`oka session` supports two tool sets:

```bash
oka session                   # default: demo.* tools (no Keynote required)
oka session --tools demo      # same as default
oka session --tools keynote   # real Keynote automation via AppleScript
```

When `--tools keynote` is selected, macOS may prompt for permission to control Keynote via Automation. Grant the permission when asked.

### Theme and layout discovery (change 006)

Discover installed themes and document layouts at runtime so the agent works
across Keynote versions and user machines without hard-coded layout names:

```text
oka> Use tool keynote.list_themes
oka> Use tool keynote.create_document with name three-pigs and theme Parchment
oka> Use tool keynote.list_layouts
oka> Use tool keynote.resolve_layout with layout title_body
oka> Use tool keynote.add_slide with layout title_body
```

`Parchment` is the recommended built-in storybook theme when available. The
semantic layout names (`title`, `title_body`, `blank`) are stable across themes;
the adapter resolves them to the actual Keynote master slide name at runtime.

### Keynote tools

| Tool | Mutating | Description |
|---|---|---|
| `keynote.list_themes` | no | Return installed Keynote theme names. |
| `keynote.create_document` | yes | Create a new document, optionally with a named theme. |
| `keynote.list_layouts` | no | Return slide layout names for the front document. |
| `keynote.resolve_layout` | no | Resolve a semantic layout name to a real Keynote name. |
| `keynote.add_slide` | yes | Add a slide via semantic layout resolution. |
| `keynote.set_slide_title` | yes | Set the title of a slide (1-indexed). |
| `keynote.set_slide_body` | yes | Set the body text of a slide (1-indexed). |
| `keynote.export_pdf` | yes | Export the front document to PDF. |
| `keynote.get_document_info` | no | Return document name and slide count. |
| `keynote.add_text_box` | yes | Add a text box with optional font size and color. |
| `keynote.add_emoji_text` | yes | Add a large emoji as a text object. |
| `keynote.add_shape` | yes | Add an MVP default rectangle shape. |
| `keynote.move_object` | yes | Move a tracked object to a new position. |
| `keynote.resize_object` | yes | Resize a tracked object. |

### Integration tests

Skipped by default. Require macOS, Keynote installed, and Automation permission:

```bash
RUN_KEYNOTE_INTEGRATION=1 uv run python -m pytest -m keynote_integration -s
```

Normal tests do not require Keynote, `osascript`, macOS GUI access, or any special permissions.

## Keynote Roadmap

The next project direction is an interactive Keynote agent:

1. ✅ Interactive agent runtime with session state, planner, executor, tool registry, observations, and step-by-step logs.
2. ✅ Keynote AppleScript adapter (`keynote.*` tools, `oka session --tools keynote`).
3. ✅ Theme and layout discovery (`keynote.list_themes`, `keynote.list_layouts`, `keynote.resolve_layout`).
4. ✅ Object tools (`keynote.add_text_box`, `keynote.add_emoji_text`, `keynote.add_shape`, `keynote.move_object`, `keynote.resize_object`).
5. Add verification for generated `.key` and PDF outputs.
5. Expose session events through an API suitable for a future Studio UI.
