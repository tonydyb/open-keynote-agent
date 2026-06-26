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
- `asset_filename` matches `slide_{slide_index:02d}.png`.

### ImageManifest

The system SHALL define an image manifest containing:

```text
deck_title
provider
assets_dir
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

The provider SHALL write PNG output to a requested path.

The system SHALL implement `FakeImageProvider`.

`FakeImageProvider` SHALL write a valid PNG file without network access.

The system MAY implement one optional real provider behind configuration.

If a real provider is selected but not configured, the system SHALL fail with a clear error.

Unit tests SHALL NOT call the real provider.

### Caching

The system SHALL compute a prompt hash from canonical `ImageSpec` JSON and provider name.

The system SHALL reuse an existing asset when all are true:

- manifest entry exists for the slide
- provider matches
- prompt hash matches
- asset path exists

The system SHALL record cache hits with `cached=True`.

The system SHALL record new generations with `cached=False`.

The system SHALL support forced regeneration.

### Asset Generation

The system SHALL provide:

```python
generate_image_assets(deck, provider, output_dir, force=False) -> ImageManifest
```

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

The function SHALL NOT write assets outside `output_dir`.

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
- CLI output
- CLI does not call Keynote tools
