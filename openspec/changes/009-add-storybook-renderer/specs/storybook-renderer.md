# Spec: Storybook Renderer

## Purpose

Render a validated `DeckSpec` into a real Keynote storybook presentation using the built-in `Parchment` theme, deterministic layout templates, emoji visuals, and MVP rectangle decorations.

## Requirements

### Renderer Package

The system SHALL add:

```text
src/open_keynote_agent/renderers/
```

The system SHALL include:

```text
storybook.py
templates.py
```

The renderer SHALL consume `DeckSpec` from `open_keynote_agent.deck.schema`.

The renderer SHALL NOT call any LLM provider.

The renderer SHALL NOT generate raw AppleScript.

### Render Function

The system SHALL provide:

```python
render_storybook_deck(deck, registry, state, output_dir, export_pdf=True) -> RenderResult
```

The function SHALL render one Keynote slide per `SlideSpec`.

The function SHALL use existing registered `keynote.*` tools through the existing executor path.

The function SHALL stop rendering and fail clearly if any tool call fails.

`RenderResult` SHALL contain:

| Field | Type | Description |
|---|---|---|
| `deck_title` | `str` | Rendered deck title. |
| `theme` | `str` | Selected Keynote theme. |
| `slide_count` | `int` | Number of DeckSpec slides rendered. |
| `pdf_path` | `str \| None` | Exported PDF path when PDF export is enabled. |
| `output_dir` | `str` | Render output directory. |
| `tool_results` | `list[dict]` | Serialized result records from every `execute_plan` call. |

The renderer SHALL append every executed tool result to `RenderResult.tool_results`.

The CLI SHALL use `RenderResult.tool_results` as the source for `tool_results.jsonl`.

### Theme Selection

The renderer SHALL call `keynote.list_themes`.

The renderer SHALL select the first available theme from:

1. `deck.theme` when present.
2. `Parchment`.
3. `Basic White`.
4. first returned theme.

The renderer SHALL create a document with the selected theme.

### Layout Discovery

The renderer SHALL call `keynote.list_layouts` after creating the document.

Keynote creates a new document with one default slide already present. The renderer SHALL use that default slide as the rendered output for `DeckSpec.slides[0]` and SHALL NOT call `keynote.add_slide` for the first `SlideSpec`.

For `DeckSpec.slides[1:]`, the renderer SHALL call `keynote.add_slide` before rendering each slide.

The renderer SHALL require the first `SlideSpec.kind` to be `cover` for this MVP. If the first slide is not `cover`, the renderer SHALL fail before creating or mutating a Keynote document.

The renderer SHALL use semantic layouts when adding slides:

| Slide kind | Layout |
|---|---|
| `cover` | `title` |
| `characters` | `title_body` |
| `chapter` | `title_body` |
| `climax` | `title_body` |
| `lesson` | `title_body` |
| `ending` | `title` |
| `content` | `title_body` |

### Storybook Templates

The renderer SHALL use deterministic templates.

The renderer SHALL NOT ask the LLM to choose coordinates.

The renderer SHALL assume a 16:9 wide layout for this MVP.

Each template SHALL produce deterministic object IDs based on slide index and object role.

Each rendered DeckSpec slide SHALL include:

- title text
- body text when present
- at least one visual element

### Text Rendering

The renderer SHALL use `keynote.set_slide_title` for slide titles when possible.

The renderer SHALL use `keynote.add_text_box` for subtitles, body blocks, and supplemental labels.

The renderer SHALL use readable default font sizes.

The renderer SHALL NOT require custom fonts.

### Emoji Visuals

The renderer SHALL use `keynote.add_emoji_text` for emoji visuals.

The renderer SHALL render up to 4 emoji items per slide.

If a slide has no emoji, the renderer SHALL use a deterministic fallback emoji based on slide kind.

### Shape Visuals

The renderer SHALL use `keynote.add_shape` only with:

```json
{"shape": "rectangle"}
```

The renderer SHALL NOT pass `fill_color` to `keynote.add_shape`.

The renderer SHALL NOT attempt `rounded_rectangle`, `oval`, `line`, or arbitrary shape strings in this change.

`VisualSpec.decorations` SHALL be treated as conceptual notes and SHALL NOT be directly converted into unsupported Keynote shape enums.

### PDF Export

When `export_pdf=True`, the renderer SHALL call `keynote.export_pdf`.

The PDF output path SHALL be inside the render output directory.

The renderer SHALL refuse to overwrite an existing PDF.

### CLI Command

The system SHALL provide:

```bash
oka render-storybook <deck_spec.json>
```

The command SHALL support:

```text
--output PATH
--no-pdf
```

The command SHALL:

1. Read and validate `deck_spec.json`.
2. Create a unique output directory when `--output` is omitted.
3. Refuse to overwrite existing output files.
4. Register real Keynote tools with `OsascriptRunner`.
5. Render the deck.
6. Write `render_result.json`.
7. Write `tool_results.jsonl`.
8. Print the output directory and PDF path when exported.

The command SHALL warn users that macOS may ask for Automation permission to control Keynote.

The command SHALL NOT call an LLM.

### Testing

Unit tests SHALL NOT require Keynote, `osascript`, GUI access, or macOS Automation permissions.

Unit tests SHALL cover:

- theme selection fallback
- semantic layout selection
- one rendered slide per `SlideSpec`
- deterministic object IDs
- fallback emoji when `visual.emoji` is empty
- only rectangle shapes are emitted
- no `fill_color` is passed to `keynote.add_shape`
- failed tool results stop rendering
- CLI validates input DeckSpec
- CLI writes render metadata
- CLI writes `tool_results.jsonl` from `RenderResult.tool_results`
- renderer rejects DeckSpecs whose first slide is not `cover`

Integration tests SHALL remain opt-in with `RUN_KEYNOTE_INTEGRATION=1`.
