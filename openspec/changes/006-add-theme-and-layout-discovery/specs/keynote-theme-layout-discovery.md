# Spec: Keynote Theme and Layout Discovery

## Purpose

Support portable Keynote generation by discovering installed themes and document layouts at runtime. This lets the agent use built-in Keynote themes such as `Parchment` and resolve semantic layout names such as `title_body` to the actual layout names available in the current document.

## Requirements

### Theme Listing

The system SHALL provide a non-mutating tool:

```text
keynote.list_themes
```

The tool SHALL call AppleScript through the configured `ScriptRunner` and return a structured list of installed Keynote theme names.

The AppleScript builder SHALL force newline-delimited output using `AppleScript's text item delimiters`.

The system SHALL NOT parse raw AppleScript list output by splitting on commas.

The tool SHALL update session context:

```json
{
  "keynote": {
    "themes": ["Parchment", "Basic White"]
  }
}
```

### Theme-Based Document Creation

The system SHALL extend:

```text
keynote.create_document
```

with an optional `theme` string parameter.

If `theme` is omitted, the tool SHALL keep existing behavior and create a document using Keynote's default theme.

If `theme` is provided, the tool SHALL generate AppleScript equivalent to:

```applescript
make new document with properties {document theme:theme "<theme>"}
```

The theme string SHALL be escaped with `applescript_string`.

The handler SHALL record the requested theme in `context["keynote"]["theme"]` only after AppleScript succeeds.

The `name` argument SHALL remain session metadata only and SHALL NOT be included in the AppleScript document properties.

The handler MAY record `slide_count: 1` as best-effort metadata after creation, but authoritative slide count SHALL come from `keynote.get_document_info`.

### Layout Listing

The system SHALL provide a non-mutating tool:

```text
keynote.list_layouts
```

The tool SHALL inspect the front Keynote document and return a structured list of slide layout names.

The AppleScript builder SHALL force newline-delimited output using `AppleScript's text item delimiters`.

The system SHALL NOT parse layout names by splitting on commas, because real Keynote layout names may contain commas.

The tool SHALL update session context:

```json
{
  "keynote": {
    "layouts": ["Title", "Title & Bullets", "Blank"]
  }
}
```

### Semantic Layout Resolution

The system SHALL provide a non-mutating tool:

```text
keynote.resolve_layout
```

with parameter:

```json
{
  "layout": "title_body"
}
```

The system SHALL support at least these semantic layout names:

| Semantic name | Candidate Keynote layout names |
|---|---|
| `title` | `Title`, `Title Slide`, `Title Only` |
| `title_body` | `Title & Bullets`, `Title, Content`, `Title and Bullets` |
| `blank` | `Blank` |

The semantic layout table and resolver SHALL live in:

```text
src/open_keynote_agent/applescript/layout.py
```

The newline-list parser SHALL live in the same module:

```python
_parse_newline_list(text: str) -> list[str]
```

The implementation SHALL remove the existing `_LAYOUT_MAP` from `tools/keynote.py` and replace it with `LAYOUT_CANDIDATES` plus `resolve_layout_name`.

Resolution SHALL use this order:

1. If the requested layout is already an exact available layout name, return it.
2. If the requested layout is a semantic key, return the first candidate that exists in the available layout list.
3. Otherwise raise a clear error that includes the requested layout and available layout names.

If available layouts are not already in context, the tool SHALL call the layout-listing AppleScript and update context before resolving.

### Discovery-Aware Add Slide

The system SHALL update:

```text
keynote.add_slide
```

so that its `layout` argument is resolved through the semantic layout resolver before building AppleScript.

The tool SHALL no longer rely only on a hard-coded semantic-to-master mapping.

If `context["keynote"]["layouts"]` is present, the tool SHALL NOT call the layout-listing AppleScript.

The tool SHALL call the layout-listing AppleScript if `context["keynote"]["layouts"]` is not available.

### Built-In Storybook Theme

The system SHOULD document `Parchment` as the preferred built-in theme for storybook-style decks.

The system SHOULD not require users to install custom themes for the open-source default workflow.

### Testing

Unit tests SHALL use `FakeScriptRunner`.

Existing `keynote.add_slide` unit tests SHALL be updated to either pre-populate `context["keynote"]["layouts"]` or configure a fake `keynote.list_layouts` response.

Real Keynote integration tests SHALL remain skipped unless `RUN_KEYNOTE_INTEGRATION=1` is set.

No unit test SHALL call real `osascript` or require Keynote.
