# Tasks

## 1. Project Initialization

- [x] Initialize Python package metadata in `pyproject.toml`.
- [x] Add CLI entrypoint `oma`.
- [x] Add runtime dependencies: `typer`, `rich`, `pydantic`, `python-dotenv`.
- [x] Add optional LLM provider dependencies for Bedrock, OpenAI, and Gemini.
- [x] Add development dependencies: `pytest`, `ruff`.
- [x] Add `.env.example` with configurable LLM provider variables.
- [x] Add initial `README.md` quickstart.

## 2. Deterministic File Organizer

- [x] Implement file category mapping by extension.
- [x] Implement `classify_file(path)` with tests.
- [x] Implement `scan_folder(target_dir)` for regular files in one folder.
- [x] Implement `build_organize_plan(target_dir, categories=None)`.
- [x] Ensure destination paths are inside the target directory.
- [x] Ensure existing destination files are skipped.
- [x] Add tests for classification and plan generation.

## 3. CLI Commands

- [x] Implement `oma organize <folder> --dry-run`.
- [x] Implement `oma organize <folder> --apply`.
- [x] Render a readable move preview with `rich`.
- [x] Ask for confirmation before applying moves.
- [x] Make confirmation default to no.
- [x] Add tests for dry-run and apply behavior.

## 4. Filesystem Execution

- [x] Implement `move_files(plan)` as the only mutating filesystem operation.
- [x] Ensure `move_files` never overwrites files.
- [x] Record moved and skipped files in the result.
- [x] Add tests for conflict handling.

## 5. Runtime Logging

- [x] Implement run session creation under `.runs/<run-id>/`.
- [x] Write `request.json`.
- [x] Write `plan.json`.
- [x] Append tool calls to `tool_calls.jsonl`.
- [x] Write `result.json`.
- [x] Add tests or smoke checks for log creation.

## 6. LLM Abstraction

- [x] Define provider-neutral `LLMClient` protocol.
- [x] Define provider selection through `OMA_LLM_PROVIDER`.
- [x] Implement `FakeLLMClient` for tests.
- [x] Implement natural-language request schema validation.
- [x] Reject malformed or unsupported LLM plans with clear errors.
- [x] Add tests using `FakeLLMClient`.

## 7. LLM Provider Adapters

- [x] Implement `BedrockConverseClient` using `boto3` Bedrock Runtime.
- [x] Support configurable `AWS_PROFILE`, `AWS_REGION`, and `BEDROCK_MODEL_ID`.
- [x] Implement `OpenAIClient` using a user-provided `OPENAI_API_KEY`.
- [x] Support configurable `OPENAI_MODEL`.
- [x] Implement `GeminiClient` using a user-provided `GEMINI_API_KEY`.
- [x] Support configurable `GEMINI_MODEL`.
- [x] Load provider configuration from environment variables.
- [x] Add a concise system prompt that returns only validated JSON.
- [x] Add developer documentation for Bedrock, OpenAI, and Gemini setup.

## 8. Natural-Language Agent Command

- [x] Implement `oma ask "<request>"`.
- [x] Convert user text into a structured organize request.
- [x] Validate the target folder exists.
- [x] Build and display the move plan.
- [x] Default to dry-run.
- [x] Require explicit confirmation before applying.

## 9. Quality Bar

- [ ] Run `ruff check`.
- [ ] Run `pytest`.
- [ ] Verify no tests require cloud credentials or API keys.
- [ ] Verify dry-run never mutates files.
- [ ] Verify apply mode never overwrites existing files.
- [ ] Update README with examples and safety notes.
