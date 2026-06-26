# Design: Storybook Renderer

## Overview

This change adds a deterministic renderer that consumes `DeckSpec` from 008 and uses Keynote tools from 006/007:

```text
deck_spec.json
  -> DeckSpec.model_validate_json(...)
  -> StorybookRenderer
  -> ToolRegistry + keynote.* tools
  -> Keynote document
  -> exported PDF
```

The renderer is not an LLM planner. It does not call `complete_json`. It maps structured content into deterministic templates.

## New Module Layout

```text
src/open_keynote_agent/renderers/
  __init__.py
  storybook.py       # render_storybook_deck(...)
  templates.py       # layout templates and geometry constants
```

The renderer may import:

- `open_keynote_agent.deck.schema`
- `open_keynote_agent.agent.session.Plan`
- `open_keynote_agent.agent.session.ProposedToolCall`
- `open_keynote_agent.agent.executor.execute_plan`
- `open_keynote_agent.agent.registry.ToolRegistry`
- `open_keynote_agent.tools.keynote.register_keynote_tools`

The renderer must not import provider-specific LLM clients.

## Input And Output

Input:

```python
DeckSpec
```

or a path to `deck_spec.json` in the CLI.

Output metadata:

```python
class RenderResult(BaseModel):
    deck_title: str
    theme: str
    slide_count: int
    pdf_path: str | None
    output_dir: str
    tool_results: list[dict]
```

`tool_results` contains serialized result records from every `execute_plan` call made by the renderer. The CLI writes `tool_results.jsonl` from this field.

The renderer mutates Keynote through registered tools, so it must be exposed through an explicit render command rather than hidden inside `oka deck-plan`.

## Theme Selection

The renderer should prefer:

1. `deck.theme` when present.
2. `Parchment`.
3. `Basic White`.
4. first available Keynote theme.

The renderer should call `keynote.list_themes`, select the theme, and then call `keynote.create_document(name=deck.title, theme=selected_theme)`.

For storybook decks, `Parchment` is the preferred built-in theme because it gives warm textured defaults across user machines without bundling external assets.

## Layout Discovery

After document creation, the renderer must call `keynote.list_layouts` so `keynote.add_slide` can resolve semantic layouts against the selected theme.

Keynote creates a new document with one default slide already present. The renderer must reuse that default slide for `DeckSpec.slides[0]` and must call `keynote.add_slide` only for `DeckSpec.slides[1:]`.

Because the default first slide layout comes from the selected theme and cannot be selected through `keynote.add_slide`, this MVP requires `DeckSpec.slides[0].kind == "cover"`. If the first slide is not a cover, rendering should fail before creating or mutating a Keynote document.

For every `SlideSpec`, the renderer uses semantic layouts:

| Slide kind | Preferred semantic layout |
|---|---|
| `cover` | `title` |
| `characters` | `title_body` |
| `chapter` | `title_body` |
| `climax` | `title_body` |
| `lesson` | `title_body` |
| `ending` | `title` |
| `content` | `title_body` |

If the selected theme resolves these differently, 006's layout resolver owns that behavior.

## Storybook Templates

Use a deterministic 16:9 wide coordinate system. MVP templates assume a 1920x1080 canvas in Keynote points-like units. If Keynote uses different dimensions, this change does not attempt responsive scaling yet.

Define templates in `renderers/templates.py`.

Each template should return a list of planned tool calls:

```python
def calls_for_slide(slide: SlideSpec, *, total_slides: int) -> list[ProposedToolCall]:
    ...
```

Template rules:

- Title text appears near the top.
- Body bullets appear in a readable left or center text box.
- Emoji visuals appear as large text objects.
- Rectangle shapes are used only as simple decorative panels or separators.
- `fill_color` is not passed to `keynote.add_shape` because 007 currently rejects it.
- Object IDs are deterministic and based on slide index and role.

Example IDs:

```text
slide_01_title
slide_01_subtitle
slide_01_emoji_1
slide_01_panel
slide_08_the_end
```

## Layout Variants

The renderer should support at least these deterministic variants:

### Cover

- Add slide with `title`.
- Set default title.
- Add subtitle text box if present.
- Add a large emoji cluster near the bottom or right.
- Add one rectangle decoration panel if useful.

### Characters

- Add slide with `title_body`.
- Set default title.
- Render body bullets as a text box.
- Render up to three emoji objects in a row.

### Chapter

- Add slide with `title_body`.
- Set default title.
- Render body bullets.
- Render 1-3 emoji visuals.
- Alternate visual placement left/right based on slide index so slides do not all look identical.

### Climax

- Add slide with `title_body`.
- Use larger title/body text.
- Render dramatic emoji cluster such as wolf/wind/house when present.

### Lesson

- Add slide with `title_body`.
- Render body bullets prominently.
- Render supportive emoji/decorations.

### Ending

- Add slide with `title`.
- Set title to slide title or `The End`.
- Add final message body if present.
- Add flower/book/star emoji decorations when available.

### Content

- Add slide with `title_body`.
- Render title, body, and available emoji.

## Visual Handling

Emoji:

- Render up to 4 emoji entries per slide.
- Use `keynote.add_emoji_text`.
- If `visual.emoji` is empty, choose a simple fallback based on slide kind:
  - cover: `📖`
  - characters: `🐷`
  - climax: `🐺`
  - ending: `✨`
  - default: `⭐`

Decorations:

- Treat `visual.decorations` as human-readable notes.
- Do not convert arbitrary decoration strings into unsupported shapes.
- Use at most one `keynote.add_shape(shape="rectangle")` panel per slide for MVP visual structure.

Text:

- Use `keynote.set_slide_title` for the default title item.
- Use `keynote.add_text_box` for subtitle, body, and small decoration labels.
- Use readable font sizes.
- Do not rely on unsupported custom font families in this change.

## Execution Model

Add:

```python
def render_storybook_deck(
    deck: DeckSpec,
    registry: ToolRegistry,
    state: SessionState,
    *,
    output_dir: Path,
    export_pdf: bool = True,
) -> RenderResult: ...
```

The function should:

1. Call `keynote.list_themes`.
2. Select the theme.
3. Call `keynote.create_document`.
4. Call `keynote.list_layouts`.
5. For `DeckSpec.slides[0]`, reuse the theme's default first slide.
6. For `DeckSpec.slides[1:]`:
   - add a Keynote slide using the semantic layout
   - set slide title
   - execute object tool calls from the template
7. Optionally call `keynote.export_pdf`.
8. Return `RenderResult` with `tool_results`.

Use the existing `execute_plan` path so validation and `ToolResult` behavior stay consistent with the agent runtime.

If any tool call fails, rendering should stop and return or raise a clear error. The CLI should exit non-zero and preserve a render log if one has already been written.

## CLI Integration

Add:

```bash
uv run oka render-storybook <deck_spec.json>
```

Options:

```text
--output PATH       output directory, default .runs/<YYYYMMDDTHHMMSSZ>-storybook/
--no-pdf           skip PDF export
```

The command:

1. Reads and validates `deck_spec.json`.
2. Creates output directory.
3. Registers Keynote tools with `OsascriptRunner`.
4. Runs `render_storybook_deck`.
5. Writes `render_result.json`.
6. Writes `tool_results.jsonl`.
7. Prints the output directory and PDF path if exported.

This command is mutating. It opens and controls Keynote. It should print the same macOS Automation permission warning used by `oka session --tools keynote`.

This change does not add a `--tools` option to `render-storybook`. CLI unit tests should monkeypatch `register_keynote_tools` or `OsascriptRunner` rather than depending on a command-line fake tool switch. A future change may add a `--tools` option if interactive renderer testing needs it.

## Testing Strategy

Unit tests should use fake Keynote tools or `FakeScriptRunner` through `register_keynote_tools`.

Cover:

- theme fallback selection
- one slide per `SlideSpec`
- cover template emits title/subtitle/emoji calls
- chapter template alternates visual placement
- empty emoji list gets fallback emoji
- object IDs are deterministic
- renderer refuses invalid DeckSpec input through Pydantic
- renderer stops on failed tool result
- CLI reads `deck_spec.json` and writes render metadata

Integration smoke test remains opt-in:

```bash
RUN_KEYNOTE_INTEGRATION=1 uv run pytest -m keynote_integration
```

Smoke flow:

1. Load the Three Little Pigs fixture DeckSpec.
2. Render with real Keynote.
3. Export PDF.
4. Assert PDF exists and has non-zero size.

## Safety

- No raw AppleScript from the LLM.
- No arbitrary filesystem overwrites.
- Output paths must refuse to overwrite existing PDF/result files unless a future explicit `--overwrite` flag is added.
- Mutating Keynote operations are isolated to the explicit `render-storybook` command.
