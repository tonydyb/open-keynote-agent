# Tasks

## 1. ScriptRunner Abstraction

- [ ] Define `ScriptRunResult` (stdout, stderr, returncode, ok property).
- [ ] Define `ScriptRunner` protocol with `run(script) -> ScriptRunResult`.
- [ ] Implement `OsascriptRunner`: wraps `subprocess.run(["osascript", "-e", script])`, captures stdout/stderr, timeout 30s, raises `RuntimeError` on `TimeoutExpired`.
- [ ] Implement `FakeScriptRunner`: accepts `responses: dict[str, ScriptRunResult] | None`; records calls in `self.calls`; returns matched response or a default ok result.
- [ ] Add unit tests for `OsascriptRunner` by monkeypatching `subprocess.run`.
- [ ] Add unit tests for `FakeScriptRunner` matching, default response, and call recording.

## 2. AppleScript Builders

- [ ] Implement `scripts.applescript_string(value: str) -> str` — escapes `\` → `\\` and `"` → `\"` for safe interpolation into AppleScript double-quoted string literals.
- [ ] Implement `scripts.create_document(name)` — calls `applescript_string(name)`; builds an AppleScript that creates a new front Keynote document (the handler records the requested name in `context`, not this builder).
- [ ] Implement `scripts.add_slide(master_name)` — accepts the resolved AppleScript master name (already looked up by the handler); calls `applescript_string(master_name)`; adds a slide at the end of the front document.
- [ ] Implement `scripts.set_slide_title(slide, title)` — calls `applescript_string(title)`; sets the title item text of slide N (1-indexed).
- [ ] Implement `scripts.set_slide_body(slide, body)` — calls `applescript_string(body)`; sets the body item text of slide N (1-indexed).
- [ ] Implement `scripts.export_pdf(posix_path)` — calls `applescript_string(posix_path)`; exports the front document to the given POSIX path.
- [ ] Implement `scripts.get_document_info()` — returns name and slide count as parseable text.
- [ ] Add unit tests that assert each builder returns a non-empty string containing the expected Keynote keywords.
- [ ] Add unit tests for `applescript_string`: verify backslash and double-quote escaping, and that safe strings pass through unchanged.

## 3. Keynote Tool Handlers

- [ ] Implement `keynote.create_document` handler: runs script, records requested name in `context["keynote"]` (session-only; not a saved file name), returns observation.
- [ ] Implement `keynote.add_slide` handler: validates `layout` against the allowed enum (`title`, `title_body`, `blank`), maps to the AppleScript master name, runs script, increments `context["keynote"]["slide_count"]`, returns observation.
- [ ] Implement `keynote.set_slide_title` handler: validates slide index, runs script, returns observation.
- [ ] Implement `keynote.set_slide_body` handler: validates slide index, runs script, returns observation.
- [ ] Implement `keynote.export_pdf` handler: (1) resolve/expand path, (2) assert parent directory exists, (3) assert resolved path does not exist — raise `RuntimeError` at steps 2 or 3 without calling the runner, (4) run script, return observation with resolved path.
- [ ] Implement `keynote.get_document_info` handler: runs script, parses stdout, returns name and slide count.
- [ ] Implement `register_keynote_tools(registry, runner)` — registers all six tools with the given runner.
- [ ] Raise `RuntimeError(stderr)` on non-ok `ScriptRunResult` in all handlers.

## 4. Tool Handler Tests

- [ ] Test each handler with `FakeScriptRunner` returning a successful result.
- [ ] Test each handler with `FakeScriptRunner` returning a non-zero result; assert `ToolResult.ok=False` via executor.
- [ ] Test `get_document_info` parses AppleScript stdout correctly.
- [ ] Test that `context["keynote"]` is updated correctly after successful calls.
- [ ] Assert `FakeScriptRunner.calls` contains the correct script for each tool.

## 5. CLI Integration

- [ ] Replace fixed `register_demo_tools` call in `oka session` with a `--tools` string option (values: `demo`, `keynote`; default: `demo`).
- [ ] When `--tools keynote` is selected, call `register_keynote_tools(registry, OsascriptRunner())`.
- [ ] When `--tools demo` (or default), call `register_demo_tools(registry)` as before.
- [ ] Update `oka session --help` text to describe the `--tools` option and its valid values.
- [ ] When `--tools keynote` is selected, print a short warning before starting the REPL: "Note: macOS may prompt for permission to control Keynote via Automation."

## 6. Integration Tests (Skipped by Default)

- [ ] Add `pytest.mark.keynote_integration` marker in `pyproject.toml`.
- [ ] Write a smoke test: create document → add slide → set title → export PDF → assert PDF exists.
- [ ] Skip unless `RUN_KEYNOTE_INTEGRATION=1` environment variable is set.
- [ ] Document how to run integration tests in `CLAUDE.md` and `AGENTS.md`.

## 7. Quality Bar

- [ ] Run `ruff check` — no errors.
- [ ] Run `pytest` — all non-integration tests pass without Keynote or `osascript`.
- [ ] Confirm `oka session` (demo mode) still works unchanged.
- [ ] Confirm no unit test calls real subprocesses; `subprocess` is only monkeypatched through `open_keynote_agent.applescript.runner.subprocess.run` in `OsascriptRunner` tests.
