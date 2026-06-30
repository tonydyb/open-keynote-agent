# Spec: Deck Spec Planner

## Purpose

Convert long presentation prompts into validated `DeckSpec` JSON and a readable slide outline without mutating Keynote.

## Requirements

### Deck Package

The system SHALL add a pure planning package:

```text
src/open_keynote_agent/deck/
```

The package SHALL NOT import Keynote tools, AppleScript builders, or `OsascriptRunner`.

### Pydantic Models

The system SHALL use Pydantic v2 models.

Every DeckSpec-related model SHALL set:

```python
model_config = {"extra": "forbid"}
```

List defaults SHALL use `Field(default_factory=list)`.

### DeckSpec Model

The system SHALL define a `DeckSpec` model with at least:

```text
title
subtitle
language
source_language
content_language
source_deck_id
theme
style
slides
```

The system SHALL validate that:

- `title` is present and non-empty after stripping whitespace.
- `language` defaults to `None`.
- `source_language`, `content_language`, and `source_deck_id` default to `None`.
- `slides` is non-empty.
- `slides` length is between 1 and 20.
- slide indexes are sequential starting at 1.

### SlideSpec Model

The system SHALL define a `SlideSpec` model with at least:

```text
index
kind
title
subtitle
body
visual
layout_hint
speaker_notes
```

The system SHALL support these slide kinds:

```text
cover
characters
chapter
climax
lesson
ending
content
```

The system SHALL validate that:

- `index >= 1`.
- `title` is present and non-empty after stripping whitespace.
- every slide has a valid `visual` spec.

### VisualSpec Model

The system SHALL define a `VisualSpec` model with at least:

```text
description
emoji
decorations
placement_hint
```

The system SHALL validate that `description` is present and non-empty after stripping whitespace.

The system SHALL validate that every `emoji` list item is a non-empty string after stripping whitespace.

The system SHALL validate that every `decorations` list item is a non-empty string after stripping whitespace.

`decorations` SHALL be conceptual visual notes, not direct `keynote.add_shape` enum values.

### StyleSpec Model

The system SHALL define a `StyleSpec` model with at least:

```text
mood
audience
palette
avoid
typography
```

The system SHALL validate that `mood` is present and non-empty after stripping whitespace.

### LLM Planner

The system SHALL provide:

```python
plan_deck_spec(
    brief,
    llm_client,
    slide_count_hint=None,
    theme_hint="Parchment",
) -> DeckSpec
```

The planner SHALL reject blank briefs before calling the LLM.

The planner SHALL reject `slide_count_hint` values outside `1..20` before calling the LLM.

The planner SHALL call the existing `LLMClient.complete_json(messages, schema)` interface.

The planner SHALL pass `DeckSpec.model_json_schema()` as the schema argument.

The planner SHALL validate the LLM response using `DeckSpec.model_validate(raw)`.

Invalid model output SHALL fail with a clear validation error.

The planner SHALL instruct the LLM to infer `language` from the brief's primary language instead of relying on a hard-coded language default.

The system SHALL also provide `DeckPlanBundle` with:

```text
localized
english
```

Both fields SHALL be independently valid `DeckSpec` objects. `localized` SHALL contain reader-visible text in the brief's primary language. `english` SHALL be the image-generation and multilingual source of truth. `english` SHALL use English text and complete English `visual.description` values that name the scene subject, characters, setting, action, and style.

`DeckPlanBundle` SHALL validate that localized and english decks have the same slide count, slide indexes, and slide kinds.

The system SHALL provide `plan_deck_bundle(...) -> DeckPlanBundle`. It SHALL use `DeckPlanBundle.model_json_schema()` and one LLM call.

The planner SHALL NOT call `keynote.*` tools.

The planner SHALL NOT open Keynote.

The planner SHALL NOT write files.

### Outline Renderer

The system SHALL provide:

```python
render_deck_outline(deck: DeckSpec) -> str
```

The outline SHALL include:

- deck title
- deck subtitle when present
- theme
- style summary
- ordered slide list
- slide index
- slide kind
- slide title
- body bullets when present
- visual description
- emoji and decorations when present

### CLI Command

The system SHALL provide a non-mutating command:

```bash
oka deck-plan "<brief>"
```

The command SHALL support:

```text
--slides INTEGER
--theme TEXT
--output PATH
```

The command SHALL:

1. Load the configured LLM provider.
2. Generate a validated `DeckPlanBundle`.
3. Create a unique default output directory when `--output` is omitted.
4. Create the explicit `--output` directory when needed.
5. Refuse to overwrite an existing `request.json`, `deck_spec.json`, `deck_spec_en.json`, `outline.md`, or `outline_en.md`.
6. Write `request.json`.
7. Write `deck_spec.json`.
8. Write `deck_spec_en.json`.
9. Write `outline.md`.
10. Write `outline_en.md`.
11. Print the localized outline.

The command SHALL write JSON with `ensure_ascii=False`.

When `--output` is omitted, the command SHALL create the default directory under `.runs/` using the same timestamp naming convention as `runtime/session.py`:

```text
.runs/<YYYYMMDDTHHMMSSZ>/
```

If the timestamp directory already exists, the command SHALL use a collision suffix such as `-1`, `-2`, etc. and SHALL NOT overwrite the existing directory.

If LLM loading, LLM completion, or DeckSpec validation fails, the command SHALL:

- exit with a non-zero status.
- print a concise user-facing error.
- not write `request.json`, `deck_spec.json`, or `outline.md`.
- not leave a partially-created default output directory when `--output` was omitted.

If an explicit `--output` directory was created before a failure, the command MAY leave that empty directory, but it SHALL NOT write partial output files.

The command SHALL NOT open Keynote.

The command SHALL NOT call `keynote.*` tools.

The command SHALL NOT require macOS Automation permission.

### Three Little Pigs Example

For the Three Little Pigs prompt, the planner SHOULD produce:

- 7-8 slides
- title similar to `三只小猪与大灰狼`
- storybook/warm/children-friendly style
- visual spec for every slide
- emoji or conceptual decoration guidance for every slide
- no blue business-style direction

### Testing

Unit tests SHALL use `FakeLLMClient`.

No tests SHALL require cloud credentials, API keys, Keynote, `osascript`, or macOS Automation permissions.

Tests SHALL cover:

- valid model parsing
- invalid model rejection
- blank brief rejection before LLM call
- invalid slide count hint rejection before LLM call
- JSON schema passed to the LLM client
- outline rendering
- CLI file output
- CLI overwrite refusal
