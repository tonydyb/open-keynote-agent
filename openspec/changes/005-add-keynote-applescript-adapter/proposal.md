# Proposal: Add Keynote AppleScript Adapter

## Summary

Add a real Keynote tool adapter that plugs into the interactive agent runtime introduced in change 004. The adapter exposes `keynote.*` tools backed by AppleScript via `osascript`. Tests remain deterministic by injecting a `FakeScriptRunner` in place of the real `OsascriptRunner`.

## Motivation

Change 004 built the full session runtime with `demo.*` tools that simulate a Keynote workflow without actually automating Keynote. This change replaces those simulations with real automation for the same set of operations.

The gap to close:

- `demo.create_document` creates an in-memory dict. `keynote.create_document` should open a real Keynote window.
- `demo.export_pdf` writes a placeholder file. `keynote.export_pdf` should export the actual document.
- Tests currently exercise only in-memory state. This change must keep tests self-contained without requiring Keynote, `osascript`, or macOS automation permissions in CI.

The runtime, executor, planner, and event log from change 004 require no modification. New code is contained to: `src/open_keynote_agent/applescript/` (runner and script builders), `tools/keynote.py` (handlers), a `--tools` option in `cli.py`, and tests/docs.

## Goals

- Add a `ScriptRunner` protocol and `OsascriptRunner` implementation that wraps `subprocess.run(["osascript", "-e", ...])`.
- Add a `FakeScriptRunner` for tests that returns configurable pre-baked output without invoking a subprocess.
- Add `keynote.*` tool handlers in `tools/keynote.py`, each backed by the `ScriptRunner`.
- Add a `register_keynote_tools(registry, runner)` function that wires tool handlers to the given runner instance.
- Ensure `oka session` can optionally register Keynote tools in addition to or instead of demo tools.
- Keep all tests deterministic: no `osascript`, no Keynote process, no macOS automation permissions required.

## Non-Goals

- Do not use the Accessibility API in this change.
- Do not add JXA support (a later change can add it as an alternative runner).
- Do not implement slide layout selection, image insertion, theming, or animations.
- Do not change core runtime semantics; only add CLI tool-set selection logic in `oka session`.
- Do not remove or replace the `demo.*` tools.

## First Tool Set

| Tool | What it does |
|---|---|
| `keynote.create_document` | Opens Keynote and creates a new document. |
| `keynote.add_slide` | Adds a slide with a given layout to the front document. |
| `keynote.set_slide_title` | Sets the title text on a slide (1-indexed). |
| `keynote.set_slide_body` | Sets the body text on a slide (1-indexed). |
| `keynote.export_pdf` | Exports the front document to a PDF at a given path. |
| `keynote.get_document_info` | Returns the document name and slide count. |

## User Stories

- As a developer on macOS with Keynote installed, I can run `oka session` with Keynote tools and see real Keynote windows open.
- As a developer in CI, all tests pass without Keynote, `osascript`, or special permissions.
- As a developer, I can inject `FakeScriptRunner` into any Keynote tool test and control the AppleScript output.
- As a developer, I can add a new AppleScript-backed tool by writing one handler function and one AppleScript string — no changes to the runtime.

## Risks

- AppleScript output format varies across Keynote versions.
- `osascript` may return non-zero exit codes for user-facing Keynote errors (e.g. permission denied, document not open).
- Slide indices in AppleScript are 1-based and may behave differently when slides are deleted or reordered mid-session.
- Export path handling differs if Keynote requires a POSIX path vs an HFS path.

## Mitigations

- Parse AppleScript output conservatively; treat any unexpected output as an error and surface it to the executor.
- `ScriptRunResult` captures both stdout and stderr; errors propagate as `ToolResult.ok=False`.
- Use POSIX paths everywhere; convert only at the AppleScript boundary.
- Integration tests that actually call `osascript` are skipped unless `RUN_KEYNOTE_INTEGRATION=1` is set.

## Success Criteria

- All existing tests pass unchanged.
- New unit tests using `FakeScriptRunner` cover every `keynote.*` tool handler.
- `ruff check` passes.
- On macOS with Keynote installed and `RUN_KEYNOTE_INTEGRATION=1`, an integration smoke test creates a document, adds a slide, and exports a PDF.
