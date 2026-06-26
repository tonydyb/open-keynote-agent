# Design: Image Asset Generation

## Overview

This change adds a non-Keynote image asset pipeline:

```text
deck_spec.json
  -> DeckSpec
  -> SlideArtSpec[]
  -> ImageProvider
  -> assets/slide_01.png
  -> image_manifest.json
```

The image stage should be deterministic around planning, file naming, caching, and metadata. The actual real provider output may be nondeterministic, but the local cache should prevent unnecessary repeated calls.

## Module Layout

```text
src/open_keynote_agent/images/
  __init__.py
  schema.py       # ImageSpec, SlideArtSpec, ImageAsset, ImageManifest
  planner.py      # build_slide_art_specs(...)
  provider.py     # ImageProvider protocol, FakeImageProvider, provider loader
  generator.py    # generate_image_assets(...)
```

The image package may import `DeckSpec` and `SlideSpec`.

The image package must not import Keynote tools, AppleScript builders, or `OsascriptRunner`.

## Data Models

Use Pydantic v2 models with:

```python
model_config = {"extra": "forbid"}
```

### ImageSpec

```python
class ImageSpec(BaseModel):
    prompt: str
    negative_prompt: str | None = None
    style: str = "storybook watercolor, warm children's book illustration"
    aspect_ratio: str = "16:9"
    output_format: Literal["png"] = "png"
    seed: int | None = None
```

Validation:

- `prompt` must be non-empty.
- `aspect_ratio` must initially support `16:9`.
- `output_format` must be `png`.

### SlideArtSpec

```python
class SlideArtSpec(BaseModel):
    slide_index: int
    slide_title: str
    image: ImageSpec
    asset_filename: str
```

Validation:

- `slide_index >= 1`.
- `asset_filename` must be deterministic and match `slide_{index:02d}.png`.

### ImageAsset

```python
class ImageAsset(BaseModel):
    slide_index: int
    prompt_hash: str
    provider: str
    path: str
    cached: bool
```

### ImageManifest

```python
class ImageManifest(BaseModel):
    deck_title: str
    provider: str
    assets_dir: str
    assets: list[ImageAsset]
```

## Art Spec Planning

Add:

```python
def build_slide_art_specs(deck: DeckSpec) -> list[SlideArtSpec]: ...
```

This function is deterministic and does not call an LLM.

Prompt construction should use existing DeckSpec fields:

- deck title
- deck style mood
- deck audience
- slide title
- slide subtitle
- body bullets
- visual description
- visual emoji
- visual decorations

Prompt guidelines:

- children's storybook illustration
- warm, cute, friendly
- no text, no captions, no letters
- match the deck's language/culture only through subject matter, not embedded text
- include characters/scenes from the slide
- prefer consistent visual style across slides

Example prompt:

```text
Children's storybook watercolor illustration for "三只小猪与大灰狼".
Slide 3: 第一章 — 大毛的稻草屋.
Scene: A straw house in a sunny meadow. Include: 🐷 🌾 🏠.
Warm orange, yellow, brown, green palette. Cute, friendly, hand-painted.
No text, no captions, no letters, no watermark.
```

## Provider Abstraction

Add:

```python
class ImageProvider(Protocol):
    name: str
    def generate(self, spec: ImageSpec, output_path: Path) -> ImageGenerationResult: ...
```

`generate` writes a PNG to `output_path`.

### FakeImageProvider

`FakeImageProvider` is required.

It should create a deterministic valid PNG file without network access. It may use a tiny embedded base64 PNG or a standard-library/minimal local writer if available.

The fake provider should make tests prove:

- output path is written
- PNG signature is valid
- no network/API credentials are required

### Optional Real Provider

The implementation may add one real provider behind configuration:

```text
OKA_IMAGE_PROVIDER=fake|<real-provider-name>
```

Real provider requirements:

- optional dependency or stdlib-only HTTP implementation
- no import failure when credentials are absent
- clear error if selected provider is not configured
- writes PNG bytes to the requested output path
- tests must not call the real provider

The provider-specific API surface must be isolated in the provider adapter.

## Caching

The generator must avoid regenerating existing images when the prompt/config has not changed.

Define:

```python
prompt_hash = sha256(canonical ImageSpec JSON + provider name).hexdigest()[:16]
```

For each slide:

1. Compute prompt hash.
2. Check existing `image_manifest.json`.
3. If matching slide index, provider, prompt hash, and asset path exists, reuse it.
4. Otherwise call provider and update manifest entry.

Cache hits should be recorded as `cached=True`.

New generations should be recorded as `cached=False`.

## Asset Paths

Assets are saved under:

```text
<output_dir>/assets/
```

Filenames:

```text
slide_01.png
slide_02.png
...
```

The generator should create directories as needed.

It should refuse to write outside `output_dir`.

## Generation Function

Add:

```python
def generate_image_assets(
    deck: DeckSpec,
    provider: ImageProvider,
    *,
    output_dir: Path,
) -> ImageManifest: ...
```

Behavior:

1. Build slide art specs.
2. Create `assets/`.
3. Load existing manifest if present.
4. Generate or reuse each slide image.
5. Write `art_spec.json`.
6. Write `image_manifest.json`.
7. Return `ImageManifest`.

Manifest writes should be atomic enough for local CLI use: write to a temporary file and replace.

## CLI Integration

Add:

```bash
uv run oka generate-images <deck_spec.json>
```

Options:

```text
--output PATH       output directory, default .runs/<YYYYMMDDTHHMMSSZ>-images/
--provider TEXT     image provider, default from OKA_IMAGE_PROVIDER or fake
--force             ignore cache and regenerate
```

The command:

1. Reads and validates `DeckSpec`.
2. Creates output directory.
3. Loads image provider.
4. Calls `generate_image_assets`.
5. Prints asset directory and manifest path.

This command must not open Keynote and must not call `keynote.*`.

## Testing Strategy

Unit tests should cover:

- ImageSpec validation
- SlideArtSpec filename validation
- deterministic prompt construction
- one art spec per DeckSpec slide
- fake provider writes valid PNG
- manifest is written
- cache hit avoids provider call
- changed prompt invalidates cache
- `--force` regenerates
- CLI validates DeckSpec input
- CLI writes assets and manifest
- CLI does not import/call Keynote tools

No unit test should require real image APIs, API keys, Keynote, `osascript`, GUI access, or macOS Automation.

## Future Use

011 can add `keynote.add_image`.

012 can update the storybook renderer to consume:

```text
deck_spec.json + image_manifest.json
```

and place generated PNGs into Keynote slides.
