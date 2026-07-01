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

### Style Notes

Style notes come only from:

- `deck.style.mood`
- `deck.style.audience`
- `deck.style.typography`
- `slide.visual.decorations`
- `deck.style.palette`

The director must not inject fixed art styles such as watercolor, oil painting, 3D, cinematic, soft lighting, warm picture book, or expressive characters unless they came from DeckSpec fields.

### Provider Prompt Format

The final `prompt` should be sectioned and scene-first:

```text
Primary scene, follow exactly:
An evil queen wearing black and purple robes stands before a glowing magic mirror in a dark royal chamber.

Required subjects:
- one evil queen
- one glowing magic mirror
- dark royal chamber

Composition:
medium-wide storybook scene

Style:
magical, whimsical, warm, storybook; audience: children; palette: #FFE5D9, #FFD700

Story context:
Snow White. Use the story only as background context; do not add unrelated story elements.

No text, no captions, no letters, no watermark.
```

The story context must be after primary scene and required subjects.

### Negative Prompt Format

The final `negative_prompt` should be a comma-separated list combining:

- generic text/watermark/logo/document/UI exclusions
- `DeckSpec.style.avoid`
- `DirectedImagePrompt.forbidden_subjects`

The negative prompt should not globally forbid humans, children, animals, castles, forests, or food because those may be valid in many stories.

## Planner Integration

`build_slide_art_specs(...)` should call `build_directed_image_prompt(...)` for each selected slide.

`SlideArtSpec.image.prompt` should use `DirectedImagePrompt.prompt`.

`SlideArtSpec.image.negative_prompt` should use `DirectedImagePrompt.negative_prompt`.

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
        "negative_prompt": "..."
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
```

Behavior:

- validates DeckSpec
- parses `--slides` if supplied
- writes `art_spec.json`
- does not load or call a real provider
- does not create assets
- prints the `art_spec.json` path

Example:

```bash
uv run oka generate-images /tmp/snow-white-plan/deck_spec_en.json \
  --slides 1,4,9 \
  --dry-run \
  --output /tmp/snow-white-prompts
```

## Testing

Unit tests should cover:

- `DirectedImagePrompt` validation
- prompt starts with primary scene before story context
- required subjects appear in prompt
- forbidden subjects appear in negative prompt
- style notes come from DeckSpec only
- no fixed art style injection
- `build_slide_art_specs` uses directed prompt output
- `--dry-run` writes `art_spec.json`
- `--dry-run` does not call provider
- `--dry-run` does not require Bedrock/OpenAI credentials
- selected slide dry-run writes only selected prompts
