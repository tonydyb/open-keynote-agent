# Tasks

## 1. ScriptRunner Abstraction

- [x] Define `ScriptRunResult` (stdout, stderr, returncode, ok property).
- [x] Define `ScriptRunner` protocol with `run(script) -> ScriptRunResult`.
- [x] Implement `OsascriptRunner`: wraps `subprocess.run(["osascript", "-e", script])`, captures stdout/stderr, timeout 30s, raises `RuntimeError` on `TimeoutExpired`.
- [x] Implement `FakeScriptRunner`: accepts `responses: dict[str, ScriptRunResult] | None`; records calls in `self.calls`; returns matched response or a default ok result.
- [x] Add unit tests for `OsascriptRunner` by monkeypatching `subprocess.run`.
- [x] Add unit tests for `FakeScriptRunner` matching, default response, and call recording.

## 2. AppleScript Builders

- [x] Implement `scripts.applescript_string(value: str) -> str` — escapes `\` → `\\` and `"` → `\"` for safe interpolation into AppleScript double-quoted string literals.
- [x] Implement `scripts.create_document(name)` — calls `applescript_string(name)`; builds an AppleScript that creates a new front Keynote document (the handler records the requested name in `context`, not this builder).
- [x] Implement `scripts.add_slide(master_name)` — accepts the resolved AppleScript master name (already looked up by the handler); calls `applescript_string(master_name)`; adds a slide at the end of the front document.
- [x] Implement `scripts.set_slide_title(slide, title)` — calls `applescript_string(title)`; sets the title item text of slide N (1-indexed).
- [x] Implement `scripts.set_slide_body(slide, body)` — calls `applescript_string(body)`; sets the body item text of slide N (1-indexed).
- [x] Implement `scripts.export_pdf(posix_path)` — calls `applescript_string(posix_path)`; exports the front document to the given POSIX path.
- [x] Implement `scripts.get_document_info()` — returns name and slide count as parseable text.
- [x] Add unit tests that assert each builder returns a non-empty string containing the expected Keynote keywords.
- [x] Add unit tests for `applescript_string`: verify backslash and double-quote escaping, and that safe strings pass through unchanged.

## 3. Keynote Tool Handlers

- [x] Implement `keynote.create_document` handler: runs script, records requested name in `context["keynote"]` (session-only; not a saved file name), returns observation.
- [x] Implement `keynote.add_slide` handler: validates `layout` against the allowed enum (`title`, `title_body`, `blank`), maps to the AppleScript master name, runs script, increments `context["keynote"]["slide_count"]`, returns observation.
- [x] Implement `keynote.set_slide_title` handler: validates slide index, runs script, returns observation.
- [x] Implement `keynote.set_slide_body` handler: validates slide index, runs script, returns observation.
- [x] Implement `keynote.export_pdf` handler: (1) resolve/expand path, (2) assert parent directory exists, (3) assert resolved path does not exist — raise `RuntimeError` at steps 2 or 3 without calling the runner, (4) run script, return observation with resolved path.
- [x] Implement `keynote.get_document_info` handler: runs script, parses stdout, returns name and slide count.
- [x] Implement `register_keynote_tools(registry, runner)` — registers all six tools with the given runner.
- [x] Raise `RuntimeError(stderr)` on non-ok `ScriptRunResult` in all handlers.

## 4. Tool Handler Tests

- [x] Test each handler with `FakeScriptRunner` returning a successful result.
- [x] Test each handler with `FakeScriptRunner` returning a non-zero result; assert `ToolResult.ok=False` via executor.
- [x] Test `get_document_info` parses AppleScript stdout correctly.
- [x] Test that `context["keynote"]` is updated correctly after successful calls.
- [x] Assert `FakeScriptRunner.calls` contains the correct script for each tool.

## 5. CLI Integration

- [x] Replace fixed `register_demo_tools` call in `oka session` with a `--tools` string option (values: `demo`, `keynote`; default: `demo`).
- [x] When `--tools keynote` is selected, call `register_keynote_tools(registry, OsascriptRunner())`.
- [x] When `--tools demo` (or default), call `register_demo_tools(registry)` as before.
- [x] Update `oka session --help` text to describe the `--tools` option and its valid values.
- [x] When `--tools keynote` is selected, print a short warning before starting the REPL: "Note: macOS may prompt for permission to control Keynote via Automation."

## 6. Integration Tests (Skipped by Default)

- [x] Add `pytest.mark.keynote_integration` marker in `pyproject.toml`.
- [x] Write a smoke test: create document → add slide → set title → export PDF → assert PDF exists.
- [x] Skip unless `RUN_KEYNOTE_INTEGRATION=1` environment variable is set.
- [x] Document how to run integration tests in `CLAUDE.md` and `AGENTS.md`.

## 7. Quality Bar

- [x] Run `ruff check` — no errors.
- [x] Run `pytest` — all non-integration tests pass without Keynote or `osascript`.
- [x] Confirm `oka session` (demo mode) still works unchanged.
- [x] Confirm no unit test calls real subprocesses; `subprocess` is only monkeypatched through `open_keynote_agent.applescript.runner.subprocess.run` in `OsascriptRunner` tests.
