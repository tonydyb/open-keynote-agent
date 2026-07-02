# Design: Add Image Assets To Storybook Renderer

## Overview

012 connects two existing pipelines:

```text
008 DeckSpec
  -> 010/011 image_manifest.json + assets/slide_XX.png
  -> 012 Keynote renderer inserts those images
```

The renderer remains deterministic. It does not call an LLM and does not generate images.

## Data Flow

```text
deck_spec.json
image_manifest.json
    |
    v
load DeckSpec + ImageManifest
    |
    v
render_storybook_deck(deck, ..., image_manifest=manifest)
    |
    v
Keynote tools:
  - create document
  - add slides
  - add image assets
  - add/edit text
  - fallback emoji/shape visuals when image missing
  - export pdf
```

## Image Manifest Resolution

`image_manifest.json` stores portable paths:

```json
{
  "assets_dir": "assets",
  "assets": [
    {"slide_index": 1, "path": "assets/slide_01.png"}
  ]
}
```

012 should resolve each asset path relative to the directory containing the manifest file.

Example:

```python
manifest_dir = image_manifest_path.parent
absolute_path = manifest_dir / asset.path
```

The loader should validate:

- manifest file exists
- manifest parses as `ImageManifest`
- asset paths are relative paths
- resolved paths exist and are files
- duplicate `slide_index` entries fail clearly

The renderer should build:

```python
dict[int, Path]  # slide_index -> absolute image path
```

## Keynote Image Tool

Add a new tool:

```text
keynote.add_image
```

Input parameters:

```json
{
  "slide": 1,
  "path": "/absolute/path/to/assets/slide_01.png",
  "x": 0,
  "y": 0,
  "width": 640,
  "height": 360,
  "object_id": "slide_01_art"
}
```

Rules:

- `path` must exist and be a file before running AppleScript.
- `path` must be converted to an absolute POSIX path.
- geometry uses the same 1280x720 coordinate system as existing templates.
- `object_id` follows existing object ID validation rules.
- returned object metadata is stored in `context["keynote"]["objects"]`.
- object type is `"image"`.
- object registry entry stores `path`, `slide`, `x`, `y`, `width`, `height`, `apple_class`, and `apple_index`.
- `context["keynote"]["slides"]["N"]["objects"]` includes the image object ID.

## AppleScript Builder

Add a builder in `applescript/scripts.py`:

```python
add_image(slide: int, path: str, x: float, y: float, width: float, height: float) -> str
```

Required AppleScript shape:

```applescript
tell application "Keynote"
  tell front document
    set targetSlide to slide <slide>
    tell targetSlide
      set imageItem to make new image with properties {file:POSIX file "<escaped absolute path>"}
      set position of imageItem to {<x>, <y>}
      set width of imageItem to <width>
      set height of imageItem to <height>
      return count of images
    end tell
  end tell
end tell
```

If real Keynote rejects one property in the `make new image` record, implementation should follow the proven text-item pattern from 007: create the object first, then set position/size in separate statements.

The builder must use existing AppleScript escaping helpers for user-controlled strings.

The builder must not set Keynote object names. `object_id` is local session metadata only.

## Renderer Layout

012 should add image-aware templates while keeping current fallback behavior.

Canvas:

```text
1280 x 720
```

When an image is available, use a full-bleed image frame:

```text
x=0
y=0
width=1280
height=720
```

The image is inserted before text so subsequent text boxes render above it.

Slides 2..N with images should use the semantic `blank` layout and should not set the Keynote default title. Slide 1 may keep the default cover title.

Text for image-backed slides should be rendered as deterministic overlay text, initially near the lower part of the slide. Automatic text color, text panels, shadows, and subject-aware placement are deferred to a later change.

The important MVP behavior is that every available image is inserted on its matching slide.

## Visual Fallback Rules

If `image_manifest` is not supplied:

- preserve existing 009 emoji/shape visual behavior.

If `image_manifest` is supplied but a slide image is missing:

- do not fail by default.
- render existing emoji/shape fallback for that slide.
- optionally record a warning in `RenderResult` if the model supports warnings; otherwise rely on `tool_results.jsonl`.

If `image_manifest` contains an image for a slide index that is not present in the DeckSpec:

- ignore it by default, or warn.
- do not create extra slides.

If a manifest asset path is listed but the file does not exist:

- fail before mutating Keynote.

This distinction is important:

- missing slide in manifest: fallback visual
- listed asset file missing: error

## RenderResult

`RenderResult` remains backwards compatible. If useful, it may add optional fields:

```text
image_count: int
missing_image_slides: list[int]
```

If fields are added, CLI `render_result.json` should include them.

`tool_results` remains the source for `tool_results.jsonl`.

## CLI

Extend:

```bash
oka render-storybook <deck_spec.json>
```

Add:

```text
--images PATH
```

Example:

```bash
uv run oka render-storybook /tmp/cinderella-plan/deck_spec.json \
  --images /tmp/cinderella-art-preview/image_manifest.json \
  --output /tmp/cinderella-rendered
```

CLI behavior:

- validate DeckSpec
- validate image manifest if supplied
- fail before creating Keynote if manifest is invalid or listed files are missing
- print image manifest path when used
- preserve `--no-pdf`
- preserve no-image behavior

## Tests

Unit tests should cover:

- manifest loading and relative path resolution
- duplicate slide indexes fail
- missing listed files fail before mutation
- missing slide asset falls back to emoji
- extra manifest slide indexes do not create extra slides
- `keynote.add_image` registration and handler behavior
- `scripts.add_image` escaping and geometry
- object registry entry for image objects
- renderer emits `keynote.add_image` for matching slide assets
- renderer does not emit emoji main visual when image is present, unless using small decorative fallback
- CLI `--images` passes manifest to renderer
- `tool_results.jsonl` includes image tool results
- no-image path preserves existing 009 behavior

Integration smoke test should be opt-in:

```bash
RUN_KEYNOTE_INTEGRATION=1 uv run pytest -m keynote_integration
```

The integration test may use a small local PNG generated by `FakeImageProvider` or a checked-in/temporary PNG.
