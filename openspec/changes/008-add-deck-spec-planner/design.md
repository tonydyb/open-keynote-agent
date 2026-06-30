# Design: Deck Spec Planner

## Overview

This change introduces a structured planning artifact for full presentations:

```text
User long prompt
  -> DeckSpecPlanner
  -> DeckSpec JSON
  -> validation
  -> outline.md
  -> future renderer
```

It is intentionally separate from Keynote rendering. The planner decides what the deck should contain; later changes decide how to draw it using deterministic templates and the available Keynote tools.

## New Module Layout

```text
src/open_keynote_agent/deck/
  __init__.py
  schema.py       # DeckSpec, SlideSpec, StyleSpec, VisualSpec
  planner.py      # plan_deck_spec(...)
  outline.py      # render_deck_outline(...)
```

The `deck` package must not import `open_keynote_agent.tools.keynote` or AppleScript builders. It is a pure planning layer.

## Data Model

Use Pydantic v2 models. Every model should set:

```python
model_config = {"extra": "forbid"}
```

List defaults must use `Field(default_factory=list)`.

### DeckSpec

```python
class DeckSpec(BaseModel):
    title: str
    subtitle: str | None = None
    language: str | None = None
    source_language: str | None = None
    content_language: str | None = None
    source_deck_id: str | None = None
    theme: str | None = "Parchment"
    style: StyleSpec
    slides: list[SlideSpec]
```

Validation:

- `title` must be non-empty after stripping whitespace.
- `language` defaults to `None`; the planner prompt should ask the LLM to infer the primary language from the brief.
- `source_language`, `content_language`, and `source_deck_id` default to `None`.
- `slides` length must be between 1 and 20 for general use.
- Slide indexes must be sequential starting at 1.
- The Three Little Pigs example should produce 7-8 slides when the prompt requests that range.

### StyleSpec

```python
class StyleSpec(BaseModel):
    mood: str
    audience: str | None = None
    palette: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    typography: str | None = None
```

Example:

```json
{
  "mood": "童话绘本风，温暖可爱",
  "audience": "儿童",
  "palette": ["orange", "yellow", "brown", "green"],
  "avoid": ["blue business style"],
  "typography": "large playful titles, readable body text"
}
```

### SlideSpec

```python
class SlideSpec(BaseModel):
    index: int
    kind: Literal[
        "cover",
        "characters",
        "chapter",
        "climax",
        "lesson",
        "ending",
        "content",
    ]
    title: str
    subtitle: str | None = None
    body: list[str] = Field(default_factory=list)
    visual: VisualSpec
    layout_hint: str | None = None
    speaker_notes: str | None = None
```

Validation:

- `index >= 1`.
- `title` must be non-empty.
- Every slide must include a valid `visual` so downstream renderers never receive pure text-only slides.
- `body` items should be concise; the planner prompt should prefer short bullets over paragraphs.

### VisualSpec

```python
class VisualSpec(BaseModel):
    description: str
    emoji: list[str] = Field(default_factory=list)
    decorations: list[str] = Field(default_factory=list)
    placement_hint: str | None = None
```

`decorations` are conceptual visual notes, not direct `keynote.add_shape` enum values. This avoids coupling the planner to the current 007 rendering limits, where only the MVP `rectangle` shape is supported.

Validation:

- `description` must be non-empty after stripping whitespace.
- `emoji` entries must be non-empty strings.
- `decorations` entries must be non-empty strings.

Example:

```json
{
  "description": "Three cute pigs and a wolf in a warm storybook style",
  "emoji": ["🐷", "🐷", "🐷", "🐺"],
  "decorations": ["warm parchment frame", "small straw/wood/brick motifs"],
  "placement_hint": "large visual cluster on the right"
}
```

## Planner

Add:

```python
def plan_deck_spec(
    brief: str,
    llm_client: LLMClient,
    *,
    slide_count_hint: int | None = None,
    theme_hint: str | None = "Parchment",
) -> DeckSpec: ...
```

Also add:

```python
class DeckPlanBundle(BaseModel):
    localized: DeckSpec
    english: DeckSpec

def plan_deck_bundle(...) -> DeckPlanBundle: ...
```

Behavior:

1. Validate that `brief.strip()` is non-empty.
2. If provided, validate `1 <= slide_count_hint <= 20`.
3. Build concise system/user messages for structured deck planning.
4. Pass `DeckSpec.model_json_schema()` to `llm_client.complete_json(messages, schema)`.
5. Validate the returned dict with `DeckSpec.model_validate(raw)`.
6. Return the validated `DeckSpec`.

The prompt should instruct the model to:

- return only JSON matching the schema
- set `language` based on the brief's primary language, e.g. `zh`, `en`, or another BCP-47-style language tag when obvious
- respect the requested slide count or slide-count range in the user brief
- include a visual description for every slide
- use emoji and conceptual decorations when the brief asks for visual elements
- avoid styles explicitly rejected by the brief, such as blue business styling
- prefer built-in Keynote theme `Parchment` for storybook decks unless the user asks otherwise
- keep slide text concise and readable for the target audience
- when generating a bundle, return `localized` in the brief's primary language and `english` as the image-generation source of truth
- make every english `visual.description` a complete English visual prompt that names subject, characters, setting, action, and style
- keep localized and english slide counts, indexes, and kinds identical

The planner must not call Keynote tools and must not write files. File persistence belongs to the CLI command.

## Outline Renderer

Add:

```python
def render_deck_outline(deck: DeckSpec) -> str: ...
```

Example output:

```markdown
# 三只小猪与大灰狼

Theme: Parchment
Style: 童话绘本风，温暖可爱

## Slides

1. Cover — 三只小猪与大灰狼
   Visual: 🐷 🐷 🐷 🐺 — Three cute pigs and a wolf

2. Characters — 认识三只小猪
   Body:
   - 大毛：贪玩，喜欢稻草屋
   - 二毛：聪明一点，但还不够努力
   - 小毛：勤劳、有耐心
   Visual: 🐷 🐷 🐷 — character lineup
```

The outline is for human review and future approval. It should be stable enough for snapshot-style unit tests.

## CLI Integration

Add a non-mutating command:

```bash
uv run oka deck-plan "<brief>"
```

Options:

```text
--slides INTEGER      optional slide count hint, 1..20
--theme TEXT          optional theme hint, default Parchment
--output PATH         optional output directory, default .runs/<YYYYMMDDTHHMMSSZ>/
```

The command:

1. Loads the configured LLM provider with `load_llm_client_from_env()`.
2. Calls `plan_deck_bundle`.
3. Creates a unique output directory when `--output` is omitted.
4. If `--output` is provided, creates it if needed but fails rather than overwriting existing `request.json`, `deck_spec.json`, `deck_spec_en.json`, `outline.md`, or `outline_en.md`.
5. Writes `request.json`.
6. Writes `deck_spec.json`.
7. Writes `deck_spec_en.json`.
8. Writes `outline.md`.
9. Writes `outline_en.md`.
10. Prints the localized outline to terminal.

Both deck spec files should be written with `ensure_ascii=False` and stable indentation. `deck_spec.json` is the localized reader-visible deck. `deck_spec_en.json` is the English image-generation and multilingual source of truth.

Default output directories must use the same timestamp naming format as `runtime/session.py`:

```text
.runs/<YYYYMMDDTHHMMSSZ>/
```

If that directory already exists, the command should add a short deterministic collision suffix such as `-1`, `-2`, etc. rather than overwriting.

### CLI Failure Behavior

If LLM loading, LLM completion, or DeckSpec validation fails, the command must:

- exit with a non-zero Typer/Click failure status
- print a concise user-facing error message
- not write `request.json`, `deck_spec.json`, `deck_spec_en.json`, `outline.md`, or `outline_en.md`
- not leave a partially-created default output directory when `--output` was omitted

For an explicit `--output` directory, the command may leave the empty directory it created, but it must not write partial output files.

This command does not open Keynote, does not require macOS Automation permission, and does not mutate files outside the chosen output directory.

## Runtime Relationship

This change does not alter `oka session`. Later changes may let `oka session` create or revise a `DeckSpec`, but the first implementation should be a simple command so the planning artifact is easy to inspect and test.

## Testing Strategy

Use `FakeLLMClient`.

Cover:

- valid `DeckSpec` parses successfully
- blank titles are rejected
- invalid slide indexes are rejected
- missing or blank visuals are rejected
- slide count outside accepted range is rejected
- `plan_deck_spec` passes a JSON schema to `complete_json`
- `plan_deck_spec` validates malformed model output
- outline rendering includes title, theme, style, slide titles, body bullets, and visuals
- CLI writes `request.json`, `deck_spec.json`, and `outline.md`
- CLI refuses to overwrite existing output files
- no tests require real LLM credentials, Keynote, `osascript`, or macOS Automation permissions

## Future Renderer

The next renderer can consume `DeckSpec`:

```text
DeckSpec
  -> storybook layout templates
  -> keynote.add_text_box / add_shape / add_emoji_text
  -> PDF export
```

This separation lets the user review the deck plan before Keynote is changed.
