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
    asset_filename: str  # computed from slide_index
```

Validation:

- `slide_index >= 1`.
- `asset_filename` must be deterministic and match `slide_{index:02d}.png`.
- `asset_filename` is a Pydantic `@computed_field`, not caller input. Do not validate it with `@field_validator`; it depends on `slide_index` and should be derived to prevent mismatches.

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

Manifest paths are portable:

- `assets_dir` is the relative string `"assets"`.
- `ImageAsset.path` is relative to the directory containing `image_manifest.json`, for example `"assets/slide_01.png"`.
- Shared cache paths are not recorded as the primary asset path.

## Art Spec Planning

Add:

```python
def build_slide_art_specs(deck: DeckSpec) -> list[SlideArtSpec]: ...
```

This function is deterministic and does not call an LLM.

Prompt construction should use existing DeckSpec fields:

- deck title
- deck subtitle
- deck style mood
- deck audience
- slide title
- slide subtitle
- body bullets
- visual description
- visual emoji
- visual decorations

Prompt construction is a generic storybook prompt compiler. It must not include story-specific hardcoded anchors such as Three Little Pigs-only, Snow White-only, or Frozen-only rules. Any story-specific character or setting information must come from the `DeckSpec` fields, not from hardcoded planner branches.

Prompt guidelines:

- children's storybook illustration
- warm, cute, friendly
- no text, no captions, no letters
- match the deck's language/culture only through subject matter, not embedded text
- include characters/scenes from the slide
- prefer consistent visual style across slides
- use English model-facing instructions, while preserving user-provided titles and scene details
- convert known emoji hints into semantic English object words, for example `🐷` -> `pig`
- use a generic negative prompt for text, captions, logos, watermarks, unrelated classroom/document/poster scenes
- do not globally exclude human characters

Example prompt:

```text
Children's storybook watercolor illustration.
Story: "三只小猪与大灰狼".
Slide 3: 第一章 — 大毛的稻草屋.
Main requirement: create an illustration that directly matches this story and this slide.
Scene description: A straw house in a sunny meadow.
Visual objects: pig, straw, house.
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

`name` is an instance-visible provider identifier. Implementations may satisfy it with a class-level constant:

```python
class FakeImageProvider:
    name = "fake"
```

Do not make provider selection depend on class names.

Define a concrete provider result:

```python
class ImageGenerationResult(BaseModel):
    provider: str
    path: str
    bytes_written: int
```

`ImageGenerationResult.path` is the path actually written by the provider as a string. The provider should raise an exception with a clear message on failure instead of returning partial success.

### FakeImageProvider

`FakeImageProvider` is required.

It should create a deterministic valid PNG file without network access. It may use a tiny embedded base64 PNG or a standard-library/minimal local writer if available.

The fake provider should make tests prove:

- output path is written
- PNG signature is valid
- no network/API credentials are required

### Provider Loader And Real Providers

The implementation must support these providers in this change:

```text
OKA_IMAGE_PROVIDER=fake|bedrock
```

The `OKA_` prefix is intentional for new image settings because the CLI is now `oka`. Existing `OMA_LLM_PROVIDER` remains a legacy LLM setting and is not renamed in this change.

Provider selection:

- `fake` is the default provider when `OKA_IMAGE_PROVIDER` is unset.
- `bedrock` is the primary real provider and must be selected explicitly with `OKA_IMAGE_PROVIDER=bedrock` or `--provider bedrock`.
- `openai` is reserved for a future optional provider and is not required in this change.

Provider defaults:

```text
OKA_IMAGE_PROVIDER unset     # defaults to fake
OKA_IMAGE_PROVIDER=fake      # explicit no-network/test provider
OKA_IMAGE_PROVIDER=bedrock   # explicit primary real provider
```

Bedrock provider requirements:

- implement `BedrockImageProvider`
- load AWS credentials/region using the existing Bedrock/AWS environment conventions where possible
- read image model id from `OKA_IMAGE_MODEL`
- do not hardcode one Bedrock image model as the only supported model
- fail clearly when AWS credentials, region, model access, or provider configuration is missing
- isolate Bedrock request/response shape in the provider adapter

Optional OpenAI provider requirements:

- `OpenAIImageProvider` is reserved for a future change
- if implemented, load model id from `OKA_IMAGE_MODEL`
- fail clearly when `OPENAI_API_KEY` or model configuration is missing

General real provider requirements:

- if the provider needs third-party packages, place them in a dedicated `images` optional dependency group in `pyproject.toml`
- if no optional dependency is added, the real provider must use stdlib-only HTTP or existing project dependencies
- no import failure when credentials are absent
- clear error if selected provider is not configured
- writes PNG bytes to the requested output path
- tests must not call the real provider

The provider-specific API surface must be isolated in the provider adapter.

## Caching

The generator must avoid regenerating existing images when the prompt/config has not changed.

Define canonical prompt hashing exactly:

```python
canonical = json.dumps(
    spec.model_dump(mode="json"),
    sort_keys=True,
    ensure_ascii=False,
    separators=(",", ":"),
)
prompt_hash = sha256(f"{provider.name}\n{canonical}".encode("utf-8")).hexdigest()[:16]
```

The provider name is part of the hash, so changing providers invalidates the cache.

Shared cache is optional and only enabled when the caller supplies `cache_dir`.

```text
<cache_dir>/<prompt_hash>.png
```

When `cache_dir` is `None`, library calls do not use a shared cache. This avoids accidental cross-test or cross-call cache pollution. Same-output-directory manifest reuse still works.

For each slide:

1. Compute prompt hash.
2. If `cache_dir` is supplied, check the shared cache path for the provider/hash.
3. Check existing `image_manifest.json` when present for same-output-dir reuse.
4. If a matching cached file exists, copy it to the current run's asset path.
5. Otherwise call provider to write the current run asset file, then populate `cache_dir` when supplied.
6. Update manifest entry.

Cache hits should be recorded as `cached=True`.

New generations should be recorded as `cached=False`.

`force=True` bypasses both shared-cache and same-output-dir manifest reuse, calls the provider again, replaces the current run asset file, and refreshes the shared cache file when `cache_dir` is supplied.

## Asset Paths

Run assets are saved under:

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

It should refuse to write run artifacts outside `output_dir`. The explicit exception is a caller-supplied `cache_dir`.

`art_spec.json` contains:

```json
{
  "deck_title": "...",
  "slides": [
    {
      "slide_index": 1,
      "slide_title": "...",
      "image": { "...": "..." },
      "asset_filename": "slide_01.png"
    }
  ]
}
```

## Generation Function

Add:

```python
def generate_image_assets(
    deck: DeckSpec,
    provider: ImageProvider,
    *,
    output_dir: Path,
    force: bool = False,
    cache_dir: Path | None = None,
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

If `cache_dir` is `None`, shared cache is disabled.

Write `image_manifest.json` atomically enough for local CLI use by writing `image_manifest.json.tmp` in the same directory and then calling `Path.replace()` to replace the final manifest.

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
- SlideArtSpec computed filename behavior
- deterministic prompt construction
- one art spec per DeckSpec slide
- fake provider writes valid PNG
- manifest is written
- cache hit avoids provider call
- shared cache hits when `cache_dir` is supplied
- changed prompt invalidates cache
- `--force` regenerates
- CLI `--force` bypasses any configured cache and calls the provider again
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
