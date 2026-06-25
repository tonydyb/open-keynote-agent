# Spec: Keynote AppleScript Adapter

## Purpose

Add real Keynote automation to `open-keynote-agent` by implementing `keynote.*` tools backed by AppleScript. The tools plug into the `ToolRegistry` and `execute_plan` loop from change 004. Tests remain deterministic by injecting a fake script runner.

## Module Structure

```text
src/open_keynote_agent/
  applescript/
    runner.py      # ScriptRunResult, ScriptRunner, OsascriptRunner, FakeScriptRunner
    scripts.py     # AppleScript string builders (one function per operation)
  tools/
    keynote.py     # keynote.* handlers + register_keynote_tools(registry, runner)
```

## ScriptRunResult

```text
ScriptRunResult
  stdout: str
  stderr: str
  returncode: int
  ok: bool        # returncode == 0
```

## ScriptRunner Protocol

```python
class ScriptRunner(Protocol):
    def run(self, script: str) -> ScriptRunResult: ...
```

### OsascriptRunner

Calls `subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=30)`. Catches `TimeoutExpired` and re-raises as `RuntimeError("osascript timed out")`. Returns a `ScriptRunResult` from subprocess output.

### FakeScriptRunner

```text
FakeScriptRunner
  responses: dict[str, ScriptRunResult]    # keyed by exact script string
  calls: list[str]                         # all scripts passed to run()
```

`run(script)` records `script` in `calls`, then returns `responses[script]` if present, else `ScriptRunResult(stdout="", stderr="", returncode=0)`. Allows tests to assert both output handling and that the correct AppleScript was sent.

## AppleScript Builders (`scripts.py`)

Each function returns a self-contained AppleScript string that can be passed directly to `osascript -e`. Scripts operate on `front document` of `application "Keynote"`.

### String Escaping

`applescript_string(value: str) -> str` escapes `\` → `\\` and `"` → `\"`. Every builder that accepts a user-controlled string argument must call this helper before interpolating the value into an AppleScript double-quoted string literal. This is a hard requirement — injecting an unescaped string is a correctness bug.

| Function | Returns a script that … |
|---|---|
| `applescript_string(value)` | Returns the escaped form of `value` for safe use inside AppleScript string literals. |
| `create_document(name)` | Builds an AppleScript that opens Keynote and creates a new front document (escapes `name`; does not set a saved file name). Context update is the handler's responsibility, not this builder's. |
| `add_slide(master_name)` | Adds a new slide at the end of the front document using the given AppleScript master name (escapes `master_name`). |
| `set_slide_title(slide, title)` | Sets `default title item` text of slide N (1-indexed; escapes `title`). |
| `set_slide_body(slide, body)` | Sets `default body item` text of slide N (1-indexed; escapes `body`). |
| `export_pdf(posix_path)` | Exports the front document to the given POSIX path as PDF (escapes `posix_path`). |
| `get_document_info()` | Returns `"<name>|<slide_count>"` so the caller can split on `\|`. |

Scripts must not include `display dialog` or any UI blocking calls. All path arguments must be POSIX paths; scripts convert using `POSIX file` where required.

## Keynote Tool Handlers (`tools/keynote.py`)

Each handler is a closure over a `ScriptRunner` instance. The pattern is:

```python
def _make_<tool>(runner: ScriptRunner):
    def handler(args: dict, context: dict) -> dict:
        script = scripts.<builder>(...)
        result = runner.run(script)
        if not result.ok:
            raise RuntimeError(result.stderr or "AppleScript error")
        # update context["keynote"] if applicable
        return {"observation": "...", ...}
    return handler
```

The executor catches `RuntimeError` and records it as `ToolResult(ok=False)`. No handler suppresses errors silently.

### Tool Definitions

| Tool | Parameters | Mutating |
|---|---|---|
| `keynote.create_document` | `name: str` | yes |
| `keynote.add_slide` | `layout: str` (enum: `title`, `title_body`, `blank`) | yes |
| `keynote.set_slide_title` | `slide: int`, `title: str` | yes |
| `keynote.set_slide_body` | `slide: int`, `body: str` | yes |
| `keynote.export_pdf` | `path: str` | yes |
| `keynote.get_document_info` | _(none)_ | no |

#### Layout Vocabulary

`keynote.add_slide` validates `layout` against the following enum before running any AppleScript:

| `layout` value | AppleScript master name |
|---|---|
| `title` | `"Title Slide"` |
| `title_body` | `"Title, Content"` |
| `blank` | `"Blank"` |

An unrecognised `layout` raises `ValueError` (recorded as `ToolResult.ok=False` by the executor). The `scripts.add_slide` builder receives the resolved master name, not the raw enum value.

#### Export Safety

`keynote.export_pdf` follows this exact order:
1. Resolve and expand the path (e.g. `Path(path).expanduser().resolve()`).
2. Assert the parent directory exists; if not, raise `RuntimeError(f"Export parent directory does not exist: {resolved.parent}")`.
3. Assert the resolved path does not already exist; if it does, raise `RuntimeError(f"Export path already exists: {resolved}")` without invoking `osascript`.
4. Run the AppleScript export.

The parent directory must already exist — this change does not create it. A future `overwrite=True` argument may allow step 3 to be skipped; that is out of scope for this change.

`register_keynote_tools(registry: ToolRegistry, runner: ScriptRunner) -> None` registers all six tools. The caller supplies the runner; production code passes `OsascriptRunner()`, tests pass `FakeScriptRunner(...)`.

### context["keynote"] Schema

Tools maintain a lightweight local mirror of document state:

```text
context["keynote"]
  name: str
  slide_count: int
```

This is best-effort. `get_document_info` reads from Keynote directly and updates the mirror. Other tools increment or set fields optimistically. If Keynote reports an error, the mirror may be stale — that is acceptable for this milestone.

## CLI Change

```bash
oka session                   # default: demo.* tools (unchanged)
oka session --tools demo      # explicit demo (same as default)
oka session --tools keynote   # keynote.* tools with OsascriptRunner
```

`--tools` is a string option defaulting to `demo`. When `keynote` is selected, `register_keynote_tools(registry, OsascriptRunner())` is called; otherwise `register_demo_tools(registry)` is called. The registry is empty at startup; exactly one tool set is registered per session.

When `--tools keynote` is selected, `cli.py` must print the following warning before starting the REPL:

```
Note: macOS may prompt for permission to control Keynote via Automation.
```

## Testing

### Unit Tests (no subprocess, no Keynote)

All `keynote.*` tool handlers are tested with `FakeScriptRunner`. Tests assert:
- Correct AppleScript string was sent (`runner.calls[-1]`).
- Successful result produces correct observation and context update.
- Non-zero returncode causes `ToolResult.ok=False` with the stderr message as the error.
- `get_document_info` parses the `"<name>|<count>"` stdout format correctly.

`OsascriptRunner` is tested by monkeypatching `subprocess.run` — never calling the real `osascript`.

### Integration Tests (skipped by default)

Marked `@pytest.mark.keynote_integration`. Skipped unless `RUN_KEYNOTE_INTEGRATION=1`. Require macOS, Keynote installed, and Automation permission granted to Terminal/the test runner.

Smoke test sequence:
1. `keynote.create_document name=test`
2. `keynote.add_slide layout=title_body`
3. `keynote.set_slide_title slide=1 title="Hello"`
4. `keynote.export_pdf path=/tmp/test.pdf`
5. Assert `/tmp/test.pdf` exists and is non-empty.

## Invariants

- No unit test calls real subprocesses; `subprocess` is only monkeypatched through `open_keynote_agent.applescript.runner.subprocess.run` in `OsascriptRunner` tests.
- All `keynote.*` handlers raise `RuntimeError` on script failure; no silent fallbacks.
- `register_keynote_tools` requires the caller to supply a runner; it never constructs `OsascriptRunner` itself.
- The `demo.*` tools are not modified or removed by this change.
