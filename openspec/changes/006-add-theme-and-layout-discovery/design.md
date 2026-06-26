# Design: Keynote Theme and Layout Discovery

## Overview

This change extends the AppleScript-backed Keynote adapter from change 005 with discovery tools. It does not change the core planner, executor, registry, or session runtime.

```text
oka session --tools keynote
  -> keynote.list_themes
  -> keynote.create_document(theme="Parchment")
  -> keynote.list_layouts
  -> keynote.resolve_layout(layout="title_body")
  -> keynote.add_slide(layout="title_body")
```

The goal is to stop hard-coding a single Keynote layout name for every user. Instead, the adapter discovers actual theme/layout names from the user's Keynote installation and document.

## Theme Discovery

Add an AppleScript builder:

```python
def list_themes() -> str: ...
```

The script MUST return newline-delimited text. AppleScript lists print as comma-separated text when returned directly through `osascript`, so the builder MUST force newline output with `AppleScript's text item delimiters`.

Required AppleScript pattern:

```applescript
set oldDelimiters to AppleScript's text item delimiters
set AppleScript's text item delimiters to "\n"
set output to (name of every theme) as text
set AppleScript's text item delimiters to oldDelimiters
return output
```

This is required because comma-splitting is unsafe: some Keynote layout names may themselves contain commas.

The handler parses stdout as newline-delimited text:

```text
Basic White
Parchment
Craft
...
```

The handler parses stdout into:

```json
{
  "themes": ["Basic White", "Parchment", "Craft"]
}
```

The handler also stores the list in session context:

```json
context["keynote"]["themes"] = [...]
```

## Create Document With Theme

Extend:

```python
scripts.create_document(name: str, theme: str | None = None) -> str
```

Behavior:

- If `theme is None`, keep the current behavior: create a new document with Keynote's default theme.
- If `theme` is provided, generate AppleScript using:

```applescript
make new document with properties {document theme:theme "<escaped theme>"}
```

The handler records:

```json
context["keynote"] = {
  "name": "three-pigs",
  "theme": "Parchment",
  "slide_count": 1
}
```

The handler should not assume the theme exists unless the script succeeds. If Keynote reports that a theme does not exist, the normal `ToolResult(ok=False)` path records the error.

The `name` argument remains session metadata only and must not be added to the AppleScript document properties. Keynote document `name` is read-only, as established in change 005.

`slide_count: 1` is best-effort metadata after creation. Theme-created Keynote documents can vary by version/theme, so `get_document_info` remains the authoritative source for the actual slide count.

## Layout Discovery

Add an AppleScript builder:

```python
def list_layouts() -> str: ...
```

It should inspect the `front document` and MUST return newline-delimited slide layout names using the same `AppleScript's text item delimiters` pattern as `list_themes`.

Required AppleScript pattern:

```applescript
set oldDelimiters to AppleScript's text item delimiters
set AppleScript's text item delimiters to "\n"
set output to (name of every master slide of front document) as text
set AppleScript's text item delimiters to oldDelimiters
return output
```

The handler parses stdout as newline-delimited text:

```text
Title
Title & Bullets
Blank
...
```

The handler parses stdout into:

```json
{
  "layouts": ["Title", "Title & Bullets", "Blank"]
}
```

The handler stores:

```json
context["keynote"]["layouts"] = [...]
```

## Semantic Layout Resolution

The public tool interface should continue to use semantic layout names:

```text
title
title_body
blank
```

Add a resolver module:

```text
src/open_keynote_agent/applescript/layout.py
```

This module owns the semantic layout table and resolution logic. `scripts.py` should remain focused on AppleScript string builders, and `tools/keynote.py` should import the resolver from this module.

```python
def _parse_newline_list(text: str) -> list[str]: ...

LAYOUT_CANDIDATES = {
    "title": ["Title", "Title Slide", "Title Only"],
    "title_body": ["Title & Bullets", "Title, Content", "Title and Bullets"],
    "blank": ["Blank"],
}

def resolve_layout_name(semantic: str, available: list[str]) -> str: ...
```

The existing `_LAYOUT_MAP` in `tools/keynote.py` is removed and replaced by `LAYOUT_CANDIDATES` plus `resolve_layout_name`. Do not keep both mapping tables.

Resolution rules:

1. If `semantic` is already an exact available layout name, return it.
2. If `semantic` is one of the known semantic keys, return the first candidate that exists in `available`.
3. If no candidate exists, raise `ValueError` with available choices.

Add a non-mutating tool:

```text
keynote.resolve_layout
```

Parameters:

```json
{
  "layout": "title_body"
}
```

Output:

```json
{
  "layout": "title_body",
  "resolved": "Title & Bullets"
}
```

It should prefer `context["keynote"]["layouts"]` if present. If layouts are missing, it MUST call `list_layouts()` internally through the runner, parse the result, and update context before resolving. This avoids confusing `available choices: []` errors for normal users.

## Updating `keynote.add_slide`

`keynote.add_slide` currently maps semantic values directly to fixed master names. Replace that with discovery-aware resolution:

1. Read available layouts from `context["keynote"]["layouts"]`.
2. If present, do not call the `list_layouts` script.
3. If missing, call the `list_layouts` script and update context.
4. Resolve the requested `layout` with `resolve_layout_name`.
5. Build `scripts.add_slide(resolved_layout_name)`.
6. Run AppleScript.

This keeps `keynote.add_slide layout=title_body` stable across built-in themes while avoiding raw LLM-provided layout names.

## Built-In Theme Preference

The recommended storybook theme is:

```text
Parchment
```

Future deck rendering may use this fallback order:

```text
Parchment -> Craft -> Basic White
```

This change should expose enough tools to implement that later, but it does not need to build the full fallback renderer yet.

## Tool Definitions

New or changed tools:

| Tool | Parameters | Mutating | Description |
|---|---|---|---|
| `keynote.list_themes` | none | no | Return installed Keynote theme names. |
| `keynote.create_document` | `name: str`, `theme?: str` | yes | Create a new front document, optionally using a named theme. |
| `keynote.list_layouts` | none | no | Return slide layout names for the front document. |
| `keynote.resolve_layout` | `layout: str` | no | Resolve semantic layout name to a real layout name. |
| `keynote.add_slide` | `layout: str` | yes | Add a slide using a resolved layout name. |

Existing tools remain:

```text
keynote.set_slide_title
keynote.set_slide_body
keynote.export_pdf
keynote.get_document_info
```

## Testing Strategy

Unit tests use `FakeScriptRunner`.

Cover:

- `scripts.list_themes()` and parsing.
- `scripts.list_layouts()` and parsing.
- `scripts.create_document(..., theme="Parchment")` includes escaped `document theme`.
- `resolve_layout_name()` chooses the first available candidate.
- `resolve_layout_name()` rejects unknown layouts with a useful error.
- `keynote.list_themes` updates context.
- `keynote.list_layouts` updates context.
- `keynote.resolve_layout` can use cached layouts.
- `keynote.resolve_layout` can fetch layouts if absent.
- `keynote.add_slide` resolves `title_body` to `Title & Bullets` when that layout exists.

Real Keynote integration tests remain skipped unless:

```bash
RUN_KEYNOTE_INTEGRATION=1
```

Add or update a smoke test that:

1. Lists themes.
2. Selects `Parchment` if present in the returned theme list.
3. Otherwise selects `Basic White` if present.
4. Otherwise selects the first returned theme.
5. Creates a document with the selected theme.
6. Lists layouts.
7. Adds a `title_body` slide through semantic resolution.
8. Exports PDF.

## Safety

- Continue escaping all AppleScript string literals.
- Continue rejecting export overwrites.
- Do not execute raw AppleScript from the LLM.
- Keep mutating tools behind the existing approval flow.
