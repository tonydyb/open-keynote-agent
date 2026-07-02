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

`ImageSpec.style` SHALL default to a neutral value such as `deck-specified`. It SHALL NOT default to a concrete art style such as watercolor, storybook, oil painting, 3D, cinematic, or soft lighting.

Later prompt-director changes MAY populate `ImageSpec.style` with a selected style mode ID when one is explicitly selected or defaulted by that change. In that case the generated `art_spec.json` SHOULD expose the actual selected style mode rather than the neutral default.

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
build_slide_art_specs(
    deck: DeckSpec,
    *,
    slide_indexes: set[int] | None = None,
) -> list[SlideArtSpec]
```

The function SHALL be deterministic.

When `slide_indexes` is `None`, the function SHALL produce one `SlideArtSpec` per `SlideSpec`.

When `slide_indexes` is supplied, the function SHALL produce art specs only for those `SlideSpec.index` values, preserving deck order.

When `slide_indexes` contains an index not present in the deck, the function SHALL raise a clear `ValueError` before any provider call.

The prompt SHALL include relevant DeckSpec data:

- deck title
- deck subtitle when present
- style mood
- audience when present
- slide title
- slide subtitle when present
- body bullets when present
- visual description
- emoji when present
- decorations when present
- typography when present
- avoid terms when present

The planner SHALL build a generic story context from `DeckSpec.title`, `DeckSpec.subtitle`, `SlideSpec.title`, `SlideSpec.body`, and `VisualSpec.description`.

The planner SHALL NOT contain story-specific hardcoded anchors such as Three Little Pigs-only, Snow White-only, or Frozen-only rules.

The planner SHALL NOT inject fixed art styles such as watercolor, warm picture book, soft lighting, expressive characters, cinematic lighting, or 3D. Image style SHALL come from `DeckSpec.style` and `VisualSpec` fields.

The planner SHALL phrase model-facing instructions primarily in English, while preserving user-provided story titles and scene details from the `DeckSpec`.

When known emoji hints are present, the planner SHALL convert them to semantic English object words, rather than relying only on raw emoji characters.

The prompt SHALL include a "no text, no captions, no letters, no watermark" instruction.

The generated `negative_prompt` SHALL include generic exclusions for text, captions, logos, watermarks, and unrelated classroom/document/poster scenes. It SHALL also include `DeckSpec.style.avoid` terms. It SHALL NOT globally exclude human characters, because many storybooks require human protagonists.

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

The system SHALL implement `BedrockImageProvider`, `OpenAIImageProvider`, and `GeminiImageProvider` as explicit real image providers.

The provider loader SHALL support these values in this change:

```text
fake
bedrock
openai
gemini
```

When `OKA_IMAGE_PROVIDER` is unset, the provider loader SHALL default to `fake`.

Tests and no-network local development MAY use the default `fake` provider or select it explicitly through dependency injection, `--provider fake`, or `OKA_IMAGE_PROVIDER=fake`.

Documentation SHALL present `bedrock`, `openai`, and `gemini` as supported real providers, selected explicitly with `--provider` or `OKA_IMAGE_PROVIDER`.

`BedrockImageProvider` SHALL:

- read image model id from `OKA_IMAGE_MODEL`
- read image Bedrock region from `OKA_IMAGE_AWS_REGION` when set
- fall back to `AWS_REGION` when `OKA_IMAGE_AWS_REGION` is absent
- use existing AWS profile/credential conventions where possible
- support Bedrock image model ids through adapter-level request/response handling
- fail clearly when AWS credentials, region, model access, or provider configuration is missing
- avoid hardcoding a single Bedrock model as the only supported image model

`OpenAIImageProvider` SHALL:

- read API key from `OPENAI_API_KEY`
- read image model id from `OKA_IMAGE_MODEL`, falling back to `OPENAI_IMAGE_MODEL`, then provider default
- read optional image size from `OKA_IMAGE_SIZE`
- fail clearly when `OPENAI_API_KEY` or SDK dependency is missing

`GeminiImageProvider` SHALL:

- read API key from `GEMINI_API_KEY`
- read image model id from `OKA_IMAGE_MODEL`, falling back to `GEMINI_IMAGE_MODEL`, then provider default
- fail clearly when `GEMINI_API_KEY` or SDK dependency is missing

If an optional real provider needs third-party packages, the system SHALL add them under a dedicated `images` optional dependency group in `pyproject.toml`.

If no `images` optional dependency group is added, any real provider implementation SHALL use stdlib-only HTTP or dependencies already present in the project.

New image provider environment variables SHALL use the `OKA_` prefix. The provider loader SHALL read:

```text
OKA_IMAGE_PROVIDER
OKA_IMAGE_MODEL
OKA_IMAGE_AWS_REGION
OKA_IMAGE_SIZE
```

Supported values SHALL include `fake`, `bedrock`, `openai`, and `gemini`.

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
    slide_indexes=None,
) -> ImageManifest
```

When `cache_dir` is `None`, shared cache SHALL be disabled.

When `slide_indexes` is `None`, the function SHALL generate or reuse assets for every slide.

When `slide_indexes` is supplied, the function SHALL generate or reuse assets only for the selected slides.

For selected-slide runs, `art_spec.json` and `image_manifest.json` SHALL describe only the selected slides for that invocation.

Selected-slide runs SHALL NOT delete existing files for unselected slides under `output_dir`.

The function SHALL:

1. Build slide art specs.
2. Create `<output_dir>/assets/`.
3. Load existing `image_manifest.json` when present.
4. Generate or reuse `slide_XX.png` for each selected slide.
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

For real image generation, callers SHOULD pass `deck_spec_en.json` produced by `oka deck-plan` when it is available. `deck_spec_en.json` is the English image-generation source of truth. The command SHALL still accept any valid `DeckSpec`, including localized `deck_spec.json`, but it SHALL NOT translate localized content itself.

The command SHALL support:

```text
--output PATH
--provider TEXT
--slides TEXT
--force
```

`--slides` SHALL accept comma-separated positive slide indexes and inclusive ranges, for example:

```text
1,4,9-12
```

When `--slides` is omitted, the command SHALL generate all slides.

Invalid selectors such as `1,,2`, `a`, `0`, or `3-1` SHALL fail before image generation.

Selectors containing slide indexes absent from the deck SHALL fail before image generation with a clear error, for example:

```text
slide 99 does not exist in deck; available slides: 1-18
```

The command SHALL:

1. Read and validate `DeckSpec`.
2. Create a unique default output directory when `--output` is omitted.
3. Load the selected image provider.
4. Parse and validate `--slides` when supplied.
5. Generate or reuse assets.
6. Write `art_spec.json`.
7. Write `image_manifest.json`.
8. Print asset directory and manifest path.

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
- selected slide generation through `slide_indexes`
- CLI `--slides` output and validation
- CLI output
- CLI does not call Keynote tools
