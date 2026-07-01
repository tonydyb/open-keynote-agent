# Design: Image Prompt Director

## Overview

This change upgrades image prompt planning from a loose paragraph prompt to a deterministic, scene-first prompt director.

```text
DeckSpec
  -> DirectedImagePrompt[]
  -> SlideArtSpec[]
  -> art_spec.json
  -> ImageProvider only when not dry-run
```

The director is part of the `images` package. It may import `DeckSpec`, `SlideSpec`, `VisualSpec`, and existing `ImageSpec` / `SlideArtSpec` models. It must not import Keynote tools, AppleScript builders, `OsascriptRunner`, or LLM providers.

## Module Layout

Add or update:

```text
src/open_keynote_agent/images/
  director.py     # DirectedImagePrompt, build_directed_image_prompt(...)
  planner.py      # consumes director output to build SlideArtSpec
  generator.py    # supports dry-run art_spec writing
```

`director.py` owns pure prompt-directing helpers. `planner.py` remains the public entry point for `build_slide_art_specs(...)`.

## Data Model

Add a Pydantic v2 model:

```python
class DirectedImagePrompt(BaseModel):
    slide_index: int
    slide_title: str
    primary_scene: str
    required_subjects: list[str] = []
    forbidden_subjects: list[str] = []
    composition: str | None = None
    style_notes: list[str] = []
    story_context: str | None = None
    prompt: str
    negative_prompt: str | None = None
```

Validation:

- `slide_index >= 1`
- `slide_title` non-empty
- `primary_scene` non-empty
- `prompt` non-empty
- all list items non-empty after stripping
- `extra="forbid"`

This model is an intermediate planning artifact. `SlideArtSpec.image.prompt` and `ImageSpec.negative_prompt` remain the provider-facing fields.

## Director Algorithm

Add:

```python
def build_directed_image_prompt(deck: DeckSpec, slide: SlideSpec) -> DirectedImagePrompt:
    ...
```

The function is deterministic and does not call an LLM.

### Primary Scene

`primary_scene` is derived from:

1. `slide.visual.description`
2. `slide.title`
3. `slide.subtitle` when present
4. `slide.body` when present

The compiled provider prompt must start with the current slide scene, not the deck title.

Prompt opening:

```text
Primary scene, follow exactly:
<slide.visual.description>
```

Only after the primary scene and required subjects should the prompt include deck-level story context.

### Required Subjects

`required_subjects` are deterministic hints extracted from:

- meaningful noun phrases already present in `slide.visual.description`
- known emoji converted to English object words
- slide title and body when they describe concrete characters, settings, or objects

The first implementation may use conservative heuristics rather than full NLP. It should prefer preserving exact DeckSpec wording over inventing new story-specific facts.

Examples:

```text
Required subjects:
- evil queen
- glowing magic mirror
- dark royal chamber
```

If the system cannot confidently extract required subjects, it may leave the list empty, but the prompt still must include `primary_scene`.

### Forbidden Subjects

`forbidden_subjects` are used to reduce model drift.

The first implementation should include:

- generic forbidden subjects from 010 such as text, watermark, logo, document, poster, UI
- `DeckSpec.style.avoid`
- story-drift terms inferred from the current slide context

The system must not use story-specific hardcoded branches such as "if Snow White then forbid apple on slide 4". However, it may use generic contrast rules:

- If a concrete object appears in the deck/story but not in the current slide, it may be forbidden when it is a known high-drift object.
- If the current slide asks for a single character or "alone", forbid extra people / duplicate main character.
- If the current slide setting is exterior, forbid indoor dining / banquet table.
- If the current slide setting is mirror/royal chamber, forbid picnic, dining table, and food.

The heuristic should stay conservative. It is better to forbid obvious drift terms than to overconstrain valid story scenes.

### Composition

`composition` is optional and deterministic.

The first version may use simple defaults:

- cover: centered character, clean background, room for title overlay
- character intro: grouped character portrait
- scene/action: medium-wide storybook scene
- ending/lesson: warm closing composition

These are generic layout hints, not story-specific rules.

### Style Modes

011 should support a small deterministic style mode layer. This is not an LLM design step; it is a controlled prompt-director option that helps image models avoid drifting into photorealistic or cinematic output.

Initial style mode IDs:

- `soft_storybook_watercolor`
- `cute_hand_drawn_cartoon`
- `paper_cut_collage_storybook`
- `deck_style`

Default style mode: `soft_storybook_watercolor`.

Fixed preset modes:

- `soft_storybook_watercolor`: gentle hand-painted children's picture-book look, watercolor texture, soft edges, warm colors, simple composition, non-photorealistic characters
- `cute_hand_drawn_cartoon`: cute hand-drawn cartoon picture-book look, rounded simplified characters, expressive faces, bright friendly colors, clear child-readable shapes
- `paper_cut_collage_storybook`: paper-cut collage picture-book look, layered paper texture, simple shapes, tactile craft materials, playful depth, child-friendly composition

Custom deck mode:

- `deck_style`: use DeckSpec / VisualSpec style fields as the primary visual style source. This is the "Use My Prompt Style" option for preview.

The final Style section should contain only the selected style mode's visual style instructions.

When a fixed preset mode is selected, the Style section should use the preset as the primary style and should not automatically include `deck.style.mood`, `deck.style.typography`, `deck.style.palette`, or `slide.visual.decorations` as style instructions. `deck.style.audience` may still be included as audience context.

When `deck_style` is selected, style intent comes from:

- `deck.style.mood`
- `deck.style.audience`
- `deck.style.typography`
- `deck.style.palette`
- `slide.visual.decorations`

When `deck_style` is selected, the director must not include any fixed preset description.

The director must not inject fixed art styles outside the selected style mode.

This avoids muddled prompts such as "paper-cut collage watercolor cinematic" and gives the preview workflow clean alternatives for users who are not expert prompt writers.

The director should add negative style guardrails unless the user explicitly requested the guarded mode:

- not photorealistic
- not cinematic
- not realistic portrait
- not movie still
- not 3D render
- not adult editorial illustration

### Provider Prompt Format

The final fixed-preset `prompt` should be sectioned with a style anchor first, then the scene. The primary scene still comes before story context:

```text
Image style, follow strongly:
soft_storybook_watercolor — gentle hand-painted children's picture-book look, watercolor texture, soft edges, warm colors, simple composition, non-photorealistic characters
audience: children

Primary scene, follow exactly:
An evil queen wearing black and purple robes stands before a glowing magic mirror in a dark royal chamber.

Required subjects:
- one evil queen
- one glowing magic mirror
- dark royal chamber

Composition:
medium-wide storybook scene

Style:
Style mode:
soft_storybook_watercolor — gentle hand-painted children's picture-book look, watercolor texture, soft edges, warm colors, simple composition, non-photorealistic characters
Audience:
children

Story context:
Snow White. Use the story only as background context; do not add unrelated story elements.

No text, no captions, no letters, no watermark.
```

When `deck_style` is selected, the prompt should remain scene-first and omit the fixed-preset style anchor.

The story context must be after primary scene and required subjects.

### Negative Prompt Format

The final `negative_prompt` should be a comma-separated list combining:

- generic text/watermark/logo/document/UI exclusions
- style guardrails from the selected style mode workflow
- `DeckSpec.style.avoid`
- `DirectedImagePrompt.forbidden_subjects`

The negative prompt should not globally forbid humans, children, animals, castles, forests, or food because those may be valid in many stories.

## Planner Integration

`build_slide_art_specs(...)` should call `build_directed_image_prompt(...)` for each selected slide.

`SlideArtSpec.image.prompt` should use `DirectedImagePrompt.prompt`.

`SlideArtSpec.image.negative_prompt` should use `DirectedImagePrompt.negative_prompt`.

`SlideArtSpec.image.style` should use the selected style mode ID. This keeps `art_spec.json` human-readable and avoids the old ambiguous `deck-specified` value after 011 style modes are available.

`art_spec.json` remains backwards compatible:

```json
{
  "deck_title": "...",
  "slides": [
    {
      "slide_index": 4,
      "slide_title": "The Evil Queen",
      "image": {
        "prompt": "...",
        "negative_prompt": "...",
        "style": "soft_storybook_watercolor"
      },
      "asset_filename": "slide_04.png"
    }
  ]
}
```

Optionally, implementation may add a `directed_prompt` object to each `art_spec.json` slide entry if useful, but it must preserve existing keys.

## Dry Run

Add a prompt-only mode to `generate_image_assets`:

```python
generate_image_assets(
    deck,
    provider,
    *,
    output_dir,
    force=False,
    cache_dir=None,
    slide_indexes=None,
    dry_run=False,
) -> ImageManifest
```

When `dry_run=True`:

- build selected `SlideArtSpec`s
- write `art_spec.json`
- do not create image assets
- do not call provider
- do not require a real provider to be configured
- do not write `image_manifest.json`, or write an empty manifest only if the spec explicitly chooses that behavior

Pick one behavior and document it in implementation. Recommended: do not write `image_manifest.json` during dry-run, because no assets exist.

## CLI

Extend:

```bash
oka generate-images <deck_spec.json>
```

Add:

```text
--dry-run
--style <style-mode-id>
```

Behavior:

- validates DeckSpec
- parses `--slides` if supplied
- validates `--style` against supported style mode IDs
- writes `art_spec.json`
- does not load or call a real provider
- does not create assets
- prints the `art_spec.json` path

Example:

```bash
uv run oka generate-images /tmp/snow-white-plan/deck_spec_en.json \
  --slides 1,4,9 \
  --style soft_storybook_watercolor \
  --dry-run \
  --output /tmp/snow-white-prompts
```

## Testing

Unit tests should cover:

- `DirectedImagePrompt` validation
- fixed preset prompt starts with style anchor
- primary scene appears before story context
- `deck_style` prompt starts with primary scene
- required subjects appear in prompt
- forbidden subjects appear in negative prompt
- default style mode is `soft_storybook_watercolor`
- supported fixed preset style modes appear in prompt and style notes
- fixed preset modes do not automatically mix in `DeckSpec.style.mood`
- `deck_style` mode uses DeckSpec / VisualSpec style fields
- `deck_style` mode does not include fixed preset descriptions
- generated `ImageSpec.style` and `art_spec.json` use the selected style mode ID
- style guardrails appear in negative prompt
- unknown style mode IDs fail clearly
- no fixed art style injection outside selected style mode
- `build_slide_art_specs` uses directed prompt output
- `--dry-run` writes `art_spec.json`
- `--dry-run` does not call provider
- `--dry-run` does not require Bedrock/OpenAI credentials
- selected slide dry-run writes only selected prompts
