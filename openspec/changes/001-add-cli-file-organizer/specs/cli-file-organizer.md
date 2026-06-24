# Spec: CLI File Organizer

## Capability

`open-mac-agent` shall provide a CLI file organizer that can plan and optionally execute safe file moves based on file categories.

## Requirements

### REQ-001: Deterministic organize command

The system shall provide a CLI command that organizes files in a target directory by category without requiring an LLM.

#### Scenario: Preview file organization

Given a directory contains `report.pdf`, `photo.png`, and `notes.md`  
When the user runs `oma organize <directory> --dry-run`  
Then the system shall display a move plan  
And `report.pdf` shall be planned for `PDFs/report.pdf`  
And `photo.png` shall be planned for `Images/photo.png`  
And `notes.md` shall be planned for `Documents/notes.md`  
And no files shall be moved

#### Scenario: Apply file organization

Given a directory contains `report.pdf`  
When the user runs `oma organize <directory> --apply`  
And the user confirms the move plan  
Then the system shall create the `PDFs` category directory if needed  
And move `report.pdf` to `PDFs/report.pdf`

### REQ-002: Natural-language organize command

The system shall provide a CLI command that converts a natural-language request into a validated file organization request.

#### Scenario: Ask to organize a folder

Given an LLM provider is configured through Bedrock, OpenAI, or Gemini  
When the user runs `oma ask "帮我整理 ./demo，把 PDF、图片、文档分类"`  
Then the system shall ask the configured LLM for a structured request  
And validate the structured request  
And display the resulting move plan

#### Scenario: Natural-language command defaults to dry-run

Given a directory contains files to organize  
When the user runs `oma ask "帮我整理 ./demo"`  
Then the system shall default to dry-run behavior  
And no files shall be moved unless the user explicitly requests apply mode and confirms

### REQ-003: Confirmation before mutation

The system shall require explicit user confirmation before moving files.

#### Scenario: User rejects confirmation

Given a move plan exists  
When the system asks for confirmation  
And the user rejects or provides no confirmation  
Then no files shall be moved  
And the run result shall record that execution was cancelled

### REQ-004: No overwrite behavior

The system shall never overwrite an existing destination file.

#### Scenario: Destination already exists

Given `report.pdf` exists in the target directory  
And `PDFs/report.pdf` already exists  
When the system builds or executes the move plan  
Then the operation for `report.pdf` shall be skipped  
And the skip reason shall mention destination conflict

### REQ-005: Path safety

The system shall prevent path traversal and operations outside the target directory.

#### Scenario: Unsafe destination path

Given a generated operation has a destination outside the target directory  
When the system validates the plan  
Then the system shall reject the operation  
And no filesystem mutation shall occur

### REQ-006: Run logging

The system shall write run artifacts for each CLI execution.

#### Scenario: Run log is created

When the user runs an organize or ask command  
Then the system shall create a `.runs/<run-id>/` directory  
And write `request.json`  
And write `plan.json` when a plan is generated  
And write `tool_calls.jsonl` when tools are invoked  
And write `result.json` when execution finishes

### REQ-007: Testability without cloud credentials

The system shall support automated tests without cloud credentials, API keys, or network calls.

#### Scenario: Fake LLM client

Given automated tests are running  
When natural-language planning behavior is tested  
Then the tests shall use a fake LLM client  
And shall not call Bedrock, OpenAI, or Gemini

### REQ-008: Selectable LLM provider

The system shall allow users to choose among AWS Bedrock, OpenAI API, Gemini API, and a fake provider for tests.

#### Scenario: Use Bedrock provider

Given `OMA_LLM_PROVIDER` is set to `bedrock`  
And Bedrock configuration is present  
When the user runs `oma ask "<request>"`  
Then the system shall use the Bedrock adapter

#### Scenario: Use OpenAI provider

Given `OMA_LLM_PROVIDER` is set to `openai`  
And `OPENAI_API_KEY` is present  
When the user runs `oma ask "<request>"`  
Then the system shall use the OpenAI adapter

#### Scenario: Use Gemini provider

Given `OMA_LLM_PROVIDER` is set to `gemini`  
And `GEMINI_API_KEY` is present  
When the user runs `oma ask "<request>"`  
Then the system shall use the Gemini adapter

#### Scenario: Missing provider configuration

Given `OMA_LLM_PROVIDER` is set to a provider with missing credentials  
When the user runs `oma ask "<request>"`  
Then the system shall fail with a clear configuration error  
And no filesystem mutation shall occur
