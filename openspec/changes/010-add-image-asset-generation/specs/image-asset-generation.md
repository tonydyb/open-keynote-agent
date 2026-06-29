# Spec: Image Asset Generation

## Purpose

Generate and cache per-slide PNG illustration assets from a validated `DeckSpec` without opening or mutating Keynote.

## Requirements

### Image Package

The system SHALL add:

```text
src/open_keynote_agent/images/
```

The package SHALL include:

```text
schema.py
planner.py
provider.py
generator.py
```

The image package SHALL consume `DeckSpec`.

The image package SHALL NOT import Keynote tools, AppleScript builders, or `OsascriptRunner`.

### ImageSpec

The system SHALL define `ImageSpec` with at least:

```text
prompt
negative_prompt
style
aspect_ratio
output_format
seed
```

The system SHALL validate that:

- `prompt` is non-empty.
- `aspect_ratio` supports `16:9`.
- `output_format` is `png`.

### SlideArtSpec

The system SHALL define `SlideArtSpec` with at least:

```text
slide_index
slide_title
image
asset_filename
```

The system SHALL validate that:

- `slide_index >= 1`.

The system SHALL expose `asset_filename` as a computed field derived from `slide_index`.

The computed value SHALL be:

```text
slide_{slide_index:02d}.png
```

The system SHALL NOT accept caller-supplied `asset_filename` values that can disagree with `slide_index`.

### ImageManifest

The system SHALL define an image manifest containing:

```text
deck_title
provider
assets_dir
assets
```

`assets_dir` SHALL be the relative path string:

```text
assets
```

Each asset entry SHALL include:

```text
slide_index
prompt_hash
provider
path
cached
```

Each asset `path` SHALL be relative to the directory containing `image_manifest.json`, for example:

```text
assets/slide_01.png
```

Manifest paths SHALL be portable across machines and working directories.

### Art Spec Planner

The system SHALL provide:

```python
build_slide_art_specs(deck: DeckSpec) -> list[SlideArtSpec]
```

The function SHALL be deterministic.

The function SHALL produce one `SlideArtSpec` per `SlideSpec`.

The prompt SHALL include relevant DeckSpec data:

- deck title
- style mood
- audience when present
- slide title
- slide subtitle when present
- body bullets when present
- visual description
- emoji when present
- decorations when present

The prompt SHALL include a "no text, no captions, no letters, no watermark" instruction.

The function SHALL NOT call an LLM.

### Image Provider

The system SHALL define an `ImageProvider` protocol.

The provider SHALL expose a stable provider name.

The provider name SHALL be available as `provider.name`.

Implementations MAY satisfy this with a class-level constant, for example:

```python
class FakeImageProvider:
    name = "fake"
```

Provider loading SHALL NOT depend on Python class names.

The provider SHALL write PNG output to a requested path.

The provider protocol SHALL return a concrete `ImageGenerationResult`:

```text
provider
path
bytes_written
```

The provider SHALL raise a clear exception on failure.

The system SHALL implement `FakeImageProvider`.

`FakeImageProvider` SHALL write a valid PNG file without network access.

The system SHALL implement `BedrockImageProvider` as the primary explicit real image provider.

The system MAY implement `OpenAIImageProvider` in a future change as an optional secondary real image provider.

The provider loader SHALL support these values in this change:

```text
fake
bedrock
```

`openai` is reserved as a future provider value until `OpenAIImageProvider` is implemented.

When `OKA_IMAGE_PROVIDER` is unset, the provider loader SHALL default to `fake`.

Tests and no-network local development MAY use the default `fake` provider or select it explicitly through dependency injection, `--provider fake`, or `OKA_IMAGE_PROVIDER=fake`.

Documentation SHALL present `bedrock` as the primary real provider for real generation, selected explicitly with `--provider bedrock` or `OKA_IMAGE_PROVIDER=bedrock`.

`BedrockImageProvider` SHALL:

- read image model id from `OKA_IMAGE_MODEL`
- use existing AWS/Bedrock credential and region conventions where possible
- support Bedrock image model ids through adapter-level request/response handling
- fail clearly when AWS credentials, region, model access, or provider configuration is missing
- avoid hardcoding a single Bedrock model as the only supported image model

`OpenAIImageProvider`, if implemented, SHALL:

- read image model id from `OKA_IMAGE_MODEL`
- fail clearly when `OPENAI_API_KEY` or model configuration is missing

If an optional real provider needs third-party packages, the system SHALL add them under a dedicated `images` optional dependency group in `pyproject.toml`.

If no `images` optional dependency group is added, any real provider implementation SHALL use stdlib-only HTTP or dependencies already present in the project.

New image provider environment variables SHALL use the `OKA_` prefix. The provider loader SHALL read:

```text
OKA_IMAGE_PROVIDER
```

Supported values SHALL include `fake` and `bedrock`. `openai` is reserved for future implementation and SHALL NOT be documented as currently supported until implemented.

The legacy `OMA_LLM_PROVIDER` variable remains an LLM setting and SHALL NOT be used for image provider selection.

If a real provider is selected but not configured, the system SHALL fail with a clear error.

Unit tests SHALL NOT call the real provider.

### Caching

The system SHALL compute a prompt hash from canonical `ImageSpec` JSON and provider name using exactly:

```python
canonical = json.dumps(
    spec.model_dump(mode="json"),
    sort_keys=True,
    ensure_ascii=False,
    separators=(",", ":"),
)
prompt_hash = sha256(f"{provider.name}\n{canonical}".encode("utf-8")).hexdigest()[:16]
```

The system SHALL use a shared cache only when `cache_dir` is supplied:

```text
<cache_dir>/<prompt_hash>.png
```

When `cache_dir` is `None`, shared cache SHALL be disabled. Same-output-directory manifest reuse SHALL still work.

The system SHALL reuse an existing asset when all are true:

- cache file exists for the provider and prompt hash when `cache_dir` is supplied, or a matching same-output-dir manifest entry exists
- provider matches
- prompt hash matches
- source asset path exists

On a cache hit, the system SHALL copy the cached PNG into the current run's `assets/slide_XX.png`.

The system SHALL record cache hits with `cached=True`.

The system SHALL record new generations with `cached=False`.

The system SHALL support forced regeneration. Forced regeneration SHALL bypass shared-cache and manifest reuse, call the provider again, replace the current run asset, and refresh the shared cache file when `cache_dir` is supplied.

### Asset Generation

The system SHALL provide:

```python
generate_image_assets(
    deck,
    provider,
    *,
    output_dir,
    force=False,
    cache_dir=None,
) -> ImageManifest
```

When `cache_dir` is `None`, shared cache SHALL be disabled.

The function SHALL:

1. Build slide art specs.
2. Create `<output_dir>/assets/`.
3. Load existing `image_manifest.json` when present.
4. Generate or reuse `slide_XX.png` for each slide.
5. Write `art_spec.json`.
6. Write `image_manifest.json`.
7. Return `ImageManifest`.

The function SHALL save images as:

```text
<output_dir>/assets/slide_01.png
<output_dir>/assets/slide_02.png
...
```

The function SHALL write `art_spec.json` as:

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

The function SHALL NOT write run artifacts outside `output_dir`.

The only allowed write outside `output_dir` is the explicit caller-supplied `cache_dir`.

The function SHALL write `image_manifest.json` by first writing `image_manifest.json.tmp` in the same directory and then replacing the final file with `Path.replace()`.

### CLI Command

The system SHALL provide:

```bash
oka generate-images <deck_spec.json>
```

The command SHALL support:

```text
--output PATH
--provider TEXT
--force
```

The command SHALL:

1. Read and validate `DeckSpec`.
2. Create a unique default output directory when `--output` is omitted.
3. Load the selected image provider.
4. Generate or reuse assets.
5. Write `art_spec.json`.
6. Write `image_manifest.json`.
7. Print asset directory and manifest path.

Default output directories SHALL use:

```text
.runs/<YYYYMMDDTHHMMSSZ>-images/
```

with collision suffixes when needed.

The command SHALL NOT open Keynote.

The command SHALL NOT call `keynote.*` tools.

### Testing

Unit tests SHALL NOT require a real image API, network access, API keys, Keynote, `osascript`, GUI access, or macOS Automation permissions.

Unit tests SHALL cover:

- model validation
- prompt construction
- one art spec per slide
- fake provider PNG output
- manifest output
- cache hits
- prompt changes invalidate cache
- forced regeneration
- CLI `--force` bypasses any configured cache and regenerates
- CLI output
- CLI does not call Keynote tools
