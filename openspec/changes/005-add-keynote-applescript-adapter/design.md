# Design: Keynote AppleScript Adapter

## Overview

This change adds one new abstraction layer (`ScriptRunner`) and one new tool module (`tools/keynote.py`). Nothing in the existing runtime, planner, executor, or registry changes.

```text
oka session
  -> ToolRegistry (existing)
       keynote.* tools  <- new, backed by ScriptRunner
       demo.*   tools   <- existing, untouched
  -> Executor (existing)
  -> ScriptRunner
       OsascriptRunner  <- real: subprocess.run(["osascript", "-e", ...])
       FakeScriptRunner <- tests: returns pre-baked output
```

## New Package Layout

```text
src/open_keynote_agent/
  applescript/
    __init__.py
    runner.py      # ScriptRunner protocol, OsascriptRunner, FakeScriptRunner, ScriptRunResult
    scripts.py     # AppleScript string constants and builders

  tools/
    demo.py        # existing, unchanged
    keynote.py     # keynote.* tool handlers + register_keynote_tools()
```

## ScriptRunner

`runner.py` defines the protocol and both implementations.

```python
class ScriptRunResult:
    stdout: str
    stderr: str
    returncode: int

    @property
    def ok(self) -> bool:
        return self.returncode == 0

class ScriptRunner(Protocol):
    def run(self, script: str) -> ScriptRunResult: ...

class OsascriptRunner:
    def run(self, script: str) -> ScriptRunResult:
        # subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=30)

class FakeScriptRunner:
    def __init__(self, responses: dict[str, ScriptRunResult] | None = None) -> None: ...
    def run(self, script: str) -> ScriptRunResult: ...
    # Returns responses[script] if present, else a default ok result.
    # Records all calls in self.calls for test assertions.
```

`FakeScriptRunner` matches on the full script string. Tests that need to match on a partial key can subclass or use a callable instead of a dict. If no match is found, it returns a default `ScriptRunResult(stdout="", stderr="", returncode=0)` so tests that only care about side-effects do not need to configure every possible response.

## AppleScript Strings

`scripts.py` contains one function per operation. Each function accepts Python arguments and returns a complete AppleScript string. Script logic stays in `scripts.py`; tool handlers in `keynote.py` call script builders and pass the result to the runner.

```python
def applescript_string(value: str) -> str: ...  # escapes backslashes and double-quotes for AppleScript string literals
def create_document(name: str) -> str: ...  # creates new front document; name is session-only, not a saved file name
def add_slide(layout: str) -> str: ...
def set_slide_title(slide: int, title: str) -> str: ...
def set_slide_body(slide: int, body: str) -> str: ...
def export_pdf(posix_path: str) -> str: ...
def get_document_info() -> str: ...
```

`applescript_string(value)` escapes `\` → `\\` and `"` → `\"` so that user-controlled strings can be safely interpolated into AppleScript double-quoted string literals. Every builder that accepts a user-controlled string argument (`name`, `title`, `body`, `layout`, `posix_path`) **must** call `applescript_string` on that value before interpolating it into the script. This is a hard requirement, not optional.

Script builders must produce scripts that work against `application "Keynote"` and operate on `front document`. Path arguments must be POSIX paths; scripts convert to HFS internally if required by the Keynote scripting dictionary.

## Keynote Tools

`tools/keynote.py` exports `register_keynote_tools(registry, runner)`.

Each tool handler is a closure over `runner`:

```python
def _make_create_document(runner: ScriptRunner):
    def handler(args, context):
        script = scripts.create_document(args["name"])
        result = runner.run(script)
        if not result.ok:
            raise RuntimeError(result.stderr or "AppleScript error")
        context["keynote"] = {"name": args["name"], "slide_count": 1}
        return {"observation": f'Created document "{args["name"]}".', "name": args["name"]}
    return handler
```

### Layout Vocabulary

`keynote.add_slide` accepts a `layout` string that must be one of the following MVP values:

| `layout` value | AppleScript master name |
|---|---|
| `title` | `"Title Slide"` |
| `title_body` | `"Title, Content"` |
| `blank` | `"Blank"` |

The handler must validate `layout` against this enum and raise `ValueError` (which the executor records as `ToolResult.ok=False`) before running any AppleScript if the value is not recognised. The `scripts.add_slide` builder receives the resolved AppleScript master name, not the raw `layout` value.

### Export Safety

`keynote.export_pdf` must follow this order before running the AppleScript export:
1. Resolve and expand the path (`Path(path).expanduser().resolve()`).
2. Assert the parent directory exists; raise `RuntimeError` if not — this change does not create missing parent directories.
3. Assert the resolved path does not already exist; raise `RuntimeError(f"Export path already exists: {resolved}")` if it does, without calling the runner.
4. Run the AppleScript export.

A future `overwrite=True` argument may allow step 3 to be skipped; it is explicitly out of scope for this change.

All handlers follow the same pattern:
1. Build the AppleScript string from `scripts.py`.
2. Call `runner.run(script)`.
3. If `result.ok` is False, raise `RuntimeError(result.stderr)` — the executor catches this and records it as a failed `ToolResult`.
4. Parse `result.stdout` only if the tool needs to return data (e.g. `get_document_info`).
5. Update `context["keynote"]` to reflect known local state.
6. Return a dict with `observation` and any structured output.

`context["keynote"]` is a best-effort local mirror of document state. It lets `get_document_info` return something useful even when Keynote is not running (though it may be stale). Tools that read from Keynote (`get_document_info`) should prefer fresh AppleScript output over cached context.

## Tool Definitions

| Tool | Parameters | Mutating | AppleScript target |
|---|---|---|---|
| `keynote.create_document` | `name: str` | yes | `make new document` (name recorded in `context["keynote"]`; not a saved file name) |
| `keynote.add_slide` | `layout: str` (enum: `title`, `title_body`, `blank`) | yes | `make new slide at end` |
| `keynote.set_slide_title` | `slide: int`, `title: str` | yes | `default title item of slide N` |
| `keynote.set_slide_body` | `slide: int`, `body: str` | yes | `default body item of slide N` |
| `keynote.export_pdf` | `path: str` | yes | `export front document to ...` |
| `keynote.get_document_info` | _(none)_ | no | `name of front document`, `count of slides` |

## CLI Integration

`cli.py` already calls `register_demo_tools(registry)` at session startup. This change replaces the fixed demo registration with a `--tools` option:

```bash
oka session                   # default: demo tools
oka session --tools demo      # explicit demo (same as default)
oka session --tools keynote   # Keynote tools with OsascriptRunner
```

`--tools` accepts the string values `demo` or `keynote` (default: `demo`). When `keynote` is selected, `register_keynote_tools(registry, OsascriptRunner())` is called; otherwise `register_demo_tools(registry)` is called. The registry is empty at startup; exactly one tool set is registered per session.

When `--tools keynote` is selected, `cli.py` prints the following warning before starting the REPL:

```
Note: macOS may prompt for permission to control Keynote via Automation.
```

## Error Handling

AppleScript errors arrive as non-zero `returncode` with an error message in `stderr`. The tool handler raises `RuntimeError(stderr)`, which the executor catches and records as `ToolResult(ok=False, error=..., observation="Error in keynote.X: ...")`. This keeps the error model consistent with all other tool failures.

Timeout: `OsascriptRunner` passes `timeout=30` to `subprocess.run`. A `subprocess.TimeoutExpired` is caught and re-raised as `RuntimeError("osascript timed out")`.

## Testing Strategy

Unit tests (`tests/test_keynote_tools.py`):
- Each tool handler tested with `FakeScriptRunner`.
- Successful response produces correct `ToolResult` and updates `context["keynote"]`.
- Non-zero returncode produces `ok=False` with error message.
- `FakeScriptRunner.calls` asserts the correct AppleScript was built and sent.

Integration tests (skipped unless `RUN_KEYNOTE_INTEGRATION=1`):
- `OsascriptRunner` actually calls `osascript`.
- Smoke test: create document → add slide → export PDF → assert PDF exists.
- Marked with `pytest.mark.keynote_integration` and skipped by default.

No test imports `subprocess` or calls `osascript` unless the integration mark is active.
