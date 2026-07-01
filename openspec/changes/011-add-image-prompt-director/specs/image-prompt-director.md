# Specification: Image Prompt Director

## Purpose

Improve image-generation semantic accuracy by compiling each `SlideSpec` into a scene-first, structured image prompt before provider invocation.

## Requirements

### Scope

The system SHALL add a deterministic image prompt director.

The director SHALL NOT call an LLM.

The director SHALL NOT translate DeckSpec content.

The director SHALL NOT call image providers.

The director SHALL NOT import or call Keynote tools, AppleScript builders, or `OsascriptRunner`.

The director SHALL NOT insert images into Keynote, PPTX, or PDF.

### Directed Image Prompt Model

The system SHALL define `DirectedImagePrompt`.

`DirectedImagePrompt` SHALL include:

```text
slide_index: int
slide_title: str
primary_scene: str
required_subjects: list[str]
forbidden_subjects: list[str]
composition: str | None
style_notes: list[str]
story_context: str | None
prompt: str
negative_prompt: str | None
```

`DirectedImagePrompt` SHALL use Pydantic v2 with `extra="forbid"`.

`slide_index` SHALL be greater than or equal to 1.

`slide_title`, `primary_scene`, and `prompt` SHALL be non-empty strings after stripping whitespace.

List fields SHALL contain only non-empty strings after stripping whitespace.

### Director Function

The system SHALL provide:

```python
build_directed_image_prompt(deck: DeckSpec, slide: SlideSpec) -> DirectedImagePrompt
```

The function SHALL be deterministic.

The function SHALL NOT call an LLM.

The function SHALL derive `primary_scene` primarily from `slide.visual.description`.

The function MAY include `slide.title`, `slide.subtitle`, and `slide.body` as additional scene context.

The function SHALL preserve user-provided story and scene wording from `DeckSpec` / `SlideSpec`; it SHALL NOT introduce story-specific hardcoded facts.

### Prompt Ordering

When a fixed preset style mode is selected, the provider-facing `prompt` SHALL start with a short style anchor section named `Image style, follow strongly`.

The fixed preset style anchor SHALL include the selected style mode ID and preset description.

When `deck_style` is selected, the provider-facing `prompt` SHALL start with the current slide's primary scene.

For every style mode, the provider-facing `prompt` SHALL include the current slide's primary scene before deck-level story context.

The provider-facing `prompt` SHALL include deck-level story context only after the primary scene and required subjects.

The provider-facing `prompt` SHALL include a clear instruction that the story context is background context and must not add unrelated story elements.

The provider-facing `prompt` SHALL include:

```text
No text, no captions, no letters, no watermark.
```

### Required Subjects

The director SHALL produce `required_subjects` from available DeckSpec data.

Sources MAY include:

- `slide.visual.description`
- converted emoji object words
- `slide.title`
- `slide.subtitle`
- `slide.body`

The director SHALL prefer conservative extraction over invented details.

The provider-facing `prompt` SHALL include a "Required subjects" section when `required_subjects` is non-empty.

### Forbidden Subjects

The director SHALL produce `forbidden_subjects` to reduce model drift.

The director SHALL include generic forbidden terms for:

- text
- captions
- letters
- words
- watermark
- logo
- signature
- document
- poster
- user interface

The director SHALL include `DeckSpec.style.avoid` terms in the final negative prompt.

The director MAY add conservative slide-specific drift exclusions when the current slide context makes them clearly inappropriate.

The director SHALL NOT globally forbid human characters, children, animals, castles, forests, houses, or food.

The director SHALL NOT use story-specific branches such as:

```python
if deck.title == "Snow White": ...
```

The final `negative_prompt` SHALL include `forbidden_subjects`.

### Style Modes

The director SHALL support deterministic image style modes.

The initial style mode IDs SHALL be:

- `soft_storybook_watercolor`
- `cute_hand_drawn_cartoon`
- `paper_cut_collage_storybook`
- `deck_style`

When no style mode is explicitly supplied, the director SHALL use `soft_storybook_watercolor`.

The fixed preset modes SHALL be:

- `soft_storybook_watercolor`
- `cute_hand_drawn_cartoon`
- `paper_cut_collage_storybook`

The `deck_style` mode SHALL use DeckSpec / VisualSpec style fields as the primary visual style source instead of a fixed preset.

The `soft_storybook_watercolor` mode SHALL describe a gentle hand-painted children's picture-book look with watercolor texture, soft edges, warm colors, simple composition, and non-photorealistic characters.

The `cute_hand_drawn_cartoon` mode SHALL describe a cute hand-drawn cartoon picture-book look with rounded simplified characters, expressive faces, bright friendly colors, and clear child-readable shapes.

The `paper_cut_collage_storybook` mode SHALL describe a paper-cut collage picture-book look with layered paper texture, simple shapes, tactile craft materials, playful depth, and child-friendly composition.

The selected style mode SHALL be included in `DirectedImagePrompt.style_notes` and in the provider-facing `prompt`.

When a fixed preset mode is selected, the provider-facing prompt SHALL use that fixed preset as the primary visual style.

When a fixed preset mode is selected, the director SHALL NOT automatically include `DeckSpec.style.mood`, `DeckSpec.style.typography`, `DeckSpec.style.palette`, or `SlideSpec.visual.decorations` as primary style instructions.

When a fixed preset mode is selected, the director MAY include `DeckSpec.style.audience` as audience context if present.

When `deck_style` is selected, the director SHALL use style notes from:

- `DeckSpec.style.mood`
- `DeckSpec.style.audience`
- `DeckSpec.style.typography`
- `DeckSpec.style.palette`
- `SlideSpec.visual.decorations`

When `deck_style` is selected, the director SHALL NOT include any fixed preset description.

The director SHALL NOT inject additional fixed art styles outside the selected style mode.

The preview workflow SHOULD present `deck_style` as a separate option named "Use My Prompt Style" or equivalent, not as hidden style text mixed into the default mode.

The director SHALL add style guardrails to reduce common undesired output modes unless the user explicitly requests one of those modes.

Default style guardrails SHOULD include:

- not photorealistic
- not cinematic
- not realistic portrait
- not movie still
- not 3D render
- not adult editorial illustration

The style guardrails SHALL be included in the final `negative_prompt`.

### Planner Integration

`build_slide_art_specs(...)` SHALL use `build_directed_image_prompt(...)`.

`SlideArtSpec.image.prompt` SHALL be populated from `DirectedImagePrompt.prompt`.

`SlideArtSpec.image.negative_prompt` SHALL be populated from `DirectedImagePrompt.negative_prompt`.

`SlideArtSpec.image.style` SHALL be populated with the selected style mode ID, such as `soft_storybook_watercolor`, `cute_hand_drawn_cartoon`, `paper_cut_collage_storybook`, or `deck_style`.

Generated `art_spec.json` SHALL NOT write the legacy neutral value `deck-specified` when a concrete style mode was selected or defaulted.

Existing `SlideArtSpec` and `ImageSpec` schemas SHALL remain backwards compatible.

### Art Spec Output

`art_spec.json` SHALL remain backwards compatible with 010:

```json
{
  "deck_title": "...",
  "slides": [
    {
      "slide_index": 1,
      "slide_title": "...",
      "image": {},
      "asset_filename": "slide_01.png"
    }
  ]
}
```

The implementation MAY include additional debugging metadata for directed prompts if it preserves existing keys and remains JSON-serializable.

### Dry Run

The system SHALL support image prompt planning without image generation.

The CLI SHALL expose:

```text
oka generate-images <deck_spec.json> --dry-run
```

When `--dry-run` is used, the command SHALL:

- validate the DeckSpec
- parse and validate `--slides` when supplied
- write `art_spec.json`
- not call any image provider
- not require real provider credentials
- not generate PNG files
- not open Keynote
- not call LLMs

When `--dry-run` is used with `--slides`, `art_spec.json` SHALL contain only selected slides.

The implementation SHALL choose and document whether `image_manifest.json` is omitted or written empty during dry-run. Recommended behavior: omit `image_manifest.json` because no image assets exist.

### CLI Compatibility

When `--dry-run` is not supplied, `oka generate-images` SHALL preserve 010 behavior.

Existing options SHALL continue to work:

```text
--output
--provider
--slides
--force
```

The CLI SHALL add:

```text
--style <style-mode-id>
```

When `--style` is omitted, the CLI SHALL use `soft_storybook_watercolor`.

When `--style` is supplied, the CLI SHALL validate it against the supported style mode IDs and fail with a clear error for unknown values.

The `--style` option SHALL work in both normal generation and `--dry-run` mode.

Example preview workflow:

```bash
uv run oka generate-images /tmp/story/deck_spec_en.json \
  --slides 1,4,9 \
  --style cute_hand_drawn_cartoon \
  --dry-run \
  --output /tmp/story-prompts-cartoon
```

### Testing

Unit tests SHALL NOT require a real image API, network access, API keys, Keynote, `osascript`, GUI access, or macOS Automation permissions.

Unit tests SHALL cover:

- `DirectedImagePrompt` validation
- prompt starts with primary scene
- story context appears after primary scene
- required subjects appear in prompt
- forbidden subjects appear in negative prompt
- default style mode is `soft_storybook_watercolor`
- supported fixed preset style modes appear in prompt and style notes
- fixed preset modes do not automatically mix in `DeckSpec.style.mood`
- `deck_style` mode uses DeckSpec / VisualSpec style fields
- `deck_style` mode does not include fixed preset descriptions
- generated `ImageSpec.style` / `art_spec.json` records contain the selected style mode ID
- fixed preset prompts start with the style anchor and still include primary scene before story context
- `deck_style` prompts start with primary scene
- style guardrails appear in negative prompt
- unknown style mode IDs fail with a clear error
- no fixed art styles are injected outside the selected style mode
- story-specific branches are not required for Snow White / Three Little Pigs / Frozen examples
- `build_slide_art_specs` uses directed prompts
- CLI `--dry-run` writes `art_spec.json`
- CLI `--dry-run` does not call provider
- CLI `--dry-run --slides` writes only selected prompts
