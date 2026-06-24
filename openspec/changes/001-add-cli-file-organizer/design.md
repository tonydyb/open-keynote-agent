# Design

## Overview

This change introduces the first agent workflow:

1. Receive a CLI command.
2. Parse deterministic arguments or natural-language intent.
3. Build a structured organization plan.
4. Preview file moves.
5. Require explicit confirmation before applying changes.
6. Execute local filesystem tools.
7. Persist run artifacts.

The implementation should keep the LLM layer separate from execution. The LLM may produce a plan, but local code validates and executes that plan.

## Proposed Package Layout

```text
src/
  open_mac_agent/
    __init__.py
    cli.py

    agent/
      loop.py
      planner.py
      executor.py

    llm/
      base.py
      bedrock.py
      openai.py
      gemini.py
      fake.py

    tools/
      base.py
      classify.py
      filesystem.py

    safety/
      confirmation.py
      policies.py

    runtime/
      events.py
      session.py

tests/
  test_file_classifier.py
  test_filesystem_tools.py
  test_agent_plan.py
```

## CLI

The CLI entrypoint should be `oma`.

Required commands:

```bash
oma organize ./demo --dry-run
oma organize ./demo --apply
oma ask "帮我整理 ./demo，把 PDF、图片、文档分类"
```

`oma organize` is deterministic and does not require an LLM.

`oma ask` uses an LLM to convert natural language into a validated structured request. It should default to dry-run unless the user explicitly passes an apply option and then confirms the move plan.

## File Categories

Initial categories should be extension-based:

```text
PDFs: .pdf
Images: .jpg, .jpeg, .png, .gif, .webp, .heic, .tiff, .bmp, .svg
Documents: .doc, .docx, .txt, .md, .rtf, .pages
Spreadsheets: .xls, .xlsx, .csv, .tsv, .numbers
Presentations: .ppt, .pptx, .key
Archives: .zip, .tar, .gz, .tgz, .rar, .7z
Audio: .mp3, .wav, .m4a, .flac, .aac
Video: .mp4, .mov, .mkv, .avi, .webm
Code: .py, .js, .ts, .tsx, .jsx, .java, .go, .rs, .rb, .php, .html, .css, .json, .yaml, .yml, .toml
Others: everything else
```

The first version should classify only regular files in the target folder. Recursive organization can be added later.

## Planning Model

Use typed data structures for the execution plan.

```python
class OrganizeRequest(BaseModel):
    target_dir: Path
    categories: list[str] | None = None
    dry_run: bool = True

class MoveOperation(BaseModel):
    source: Path
    destination: Path
    category: str

class OrganizePlan(BaseModel):
    target_dir: Path
    operations: list[MoveOperation]
    skipped: list[SkippedFile]
```

Path validation must ensure operations stay under the requested target directory.

## LLM Integration

Create a provider-neutral interface:

```python
class LLMClient(Protocol):
    def complete_json(self, messages: list[dict], schema: dict) -> dict:
        ...
```

Implement:

- `BedrockConverseClient` for AWS Bedrock.
- `OpenAIClient` for user-provided OpenAI API keys.
- `GeminiClient` for user-provided Gemini API keys.
- `FakeLLMClient` for tests.

Provider adapters should expose the same `complete_json` behavior. The rest of the agent must not depend on provider-specific SDK objects.

Use:

- Bedrock Converse API through `boto3.client("bedrock-runtime")`.
- OpenAI Responses API or Chat Completions-compatible structured JSON mode, depending on the installed SDK version.
- Gemini API through the official Google Gen AI SDK or REST API.

Configuration:

```text
OMA_LLM_PROVIDER=bedrock|openai|gemini|fake

# Bedrock
AWS_PROFILE
AWS_REGION
BEDROCK_MODEL_ID

# OpenAI
OPENAI_API_KEY
OPENAI_MODEL

# Gemini
GEMINI_API_KEY
GEMINI_MODEL
```

Provider SDKs should be optional imports where practical, so a user can run the deterministic CLI without configuring all providers. Tests should use `FakeLLMClient` and must not call external LLM providers.

## Safety

The agent must:

- Default to dry-run for `oma ask`.
- Require confirmation before filesystem mutation.
- Refuse to overwrite existing destination files.
- Refuse path traversal outside the target directory.
- Refuse missing or non-directory targets.
- Never delete files in this change.

If a destination exists, the operation should be skipped and recorded. A future change can add rename strategies.

## Logging

Each run should create:

```text
.runs/
  <timestamp>-<short-id>/
    request.json
    plan.json
    tool_calls.jsonl
    result.json
```

The log should include enough detail to answer:

- What did the user request?
- What plan was generated?
- What tools were called?
- What changed?
- What was skipped and why?

## Testing Strategy

Unit tests:

- File extension classification.
- Plan generation from a temporary folder.
- Dry-run does not move files.
- Apply moves files after confirmation is simulated.
- Existing destinations are skipped.
- LLM malformed JSON is rejected.

Integration smoke test:

- Create a temporary folder with mixed files.
- Run deterministic organize in dry-run mode.
- Verify the proposed destinations.

No test should require real cloud credentials, API keys, or network access.
