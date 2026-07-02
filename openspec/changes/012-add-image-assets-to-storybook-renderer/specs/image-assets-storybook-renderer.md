# Spec: Image Assets To Storybook Renderer

## Purpose

Render a `DeckSpec` into Keynote using existing generated image assets from `image_manifest.json`.

## Requirements

### Scope

The system SHALL connect generated PNG image assets to the Keynote storybook renderer.

The system SHALL NOT generate images.

The system SHALL NOT call an LLM.

The system SHALL NOT replace the existing Keynote renderer.

The system SHALL preserve the existing no-image `render-storybook` behavior.

### Image Manifest Loading

The system SHALL load image assets from an optional `image_manifest.json`.

The loader SHALL parse the manifest using the existing `ImageManifest` schema.

The loader SHALL resolve each asset path relative to the directory containing `image_manifest.json`.

The loader SHALL reject absolute asset paths in the manifest.

The loader SHALL reject duplicate `slide_index` entries.

The loader SHALL reject manifest entries whose resolved asset path does not exist or is not a file.

The loader SHALL return a mapping from `slide_index` to absolute image path.

If an `image_manifest.json` is not supplied, the renderer SHALL behave exactly like the 009 renderer.

If an `image_manifest.json` is supplied but has no asset entry for a DeckSpec slide, that slide SHALL use the existing emoji/shape fallback visual.

If an `image_manifest.json` contains asset entries for slide indexes not present in the DeckSpec, the renderer SHALL NOT create extra slides.

### Keynote Image Tool

The system SHALL add:

```text
keynote.add_image
```

The tool SHALL accept:

```text
slide: int
path: str
x: float
y: float
width: float
height: float
object_id: str | None
```

The tool SHALL validate that:

- `slide >= 1`
- `path` exists
- `path` is a file
- `path` is converted to an absolute path before AppleScript execution
- geometry is valid using the existing object geometry validator
- `object_id`, when supplied, passes existing object ID validation

The tool SHALL call a new AppleScript builder in `applescript/scripts.py`.

The tool SHALL store image object metadata in:

```text
context["keynote"]["objects"][object_id]
```

The metadata SHALL include:

```text
object_id
slide
type = "image"
path
x
y
width
height
apple_class
apple_index
```

The tool SHALL also add the object ID to:

```text
context["keynote"]["slides"][str(slide)]["objects"]
```

### AppleScript Image Builder

The system SHALL add:

```python
scripts.add_image(slide, path, x, y, width, height) -> str
```

The builder SHALL insert a local image file into the requested slide.

The builder SHALL set:

- position
- width
- height

The builder SHALL return the created image object's collection index.

The builder SHALL escape all user-controlled strings with the existing AppleScript escaping helper.

The builder SHOULD use separate `set` statements for position and size to avoid Keynote AppleScript property-record incompatibilities.

The builder SHALL NOT set Keynote object names. `object_id` remains local session metadata because Keynote image items do not reliably expose a writable object name property.

### Renderer Image Integration

`render_storybook_deck(...)` SHALL accept optional image assets.

The renderer SHALL insert an image for each slide whose `SlideSpec.index` has a matching image asset.

The renderer SHALL insert images using `keynote.add_image` through the existing executor path.

The renderer SHALL append image insertion tool results to `RenderResult.tool_results`.

When a slide image is available, the renderer SHALL use that image as the primary visual for the slide.

When a slide image is available, the renderer SHOULD avoid rendering the previous large emoji primary visual for that slide.

When a slide image is available, the renderer SHALL insert the image before overlay text so text appears above the image.

When a slide image is available for slide 2 or later, the renderer SHALL use the semantic `blank` layout for newly added slides.

When a slide image is available for slide 2 or later, the renderer SHALL NOT set the Keynote default slide title; children's picture-book pages should avoid large presentation titles.

When a slide image is available for slide 1, the renderer MAY keep the default cover title.

When a slide image is not available, the renderer SHALL preserve the existing emoji/shape fallback visual.

The renderer SHALL keep deterministic coordinates and SHALL NOT ask an LLM to choose layout.

The renderer SHALL continue to create exactly one Keynote slide per DeckSpec slide.

The renderer SHALL NOT create extra slides for extra image manifest assets.

### Image Layout

The renderer SHALL use deterministic 16:9 coordinates.

When a slide image is available, the renderer SHALL use a full-bleed image placement:

```text
x = 0
y = 0
width = 1280
height = 720
```

When a slide image is available, the renderer SHALL place text as a deterministic overlay on top of the image.

For slide 1, overlay text MAY be limited to subtitle/body because the Keynote default title is still used for the cover.

For slides 2 and later, overlay text SHALL use `SlideSpec.body` when present; if body is empty, it MAY use subtitle or title as fallback copy.

The overlay text SHALL be rendered through `keynote.add_text_box`; automatic color selection and semi-transparent text panels are deferred to a later change.

### CLI

The system SHALL extend:

```bash
oka render-storybook <deck_spec.json>
```

with:

```text
--images PATH
```

`--images` SHALL point to `image_manifest.json`.

When `--images` is supplied, the CLI SHALL validate the manifest and files before creating or mutating a Keynote document.

The CLI SHALL pass resolved image assets into the renderer.

The CLI SHALL preserve:

- `--output`
- `--no-pdf`
- no-image rendering behavior

### Render Output

The CLI SHALL continue to write:

```text
render_result.json
tool_results.jsonl
```

`tool_results.jsonl` SHALL include `keynote.add_image` results when image assets are inserted.

`render_result.json` MAY include image-related metadata such as:

```text
image_count
missing_image_slides
```

If added, image-related fields SHALL be deterministic.

### Testing

Unit tests SHALL NOT require real Keynote, `osascript`, GUI access, or macOS Automation permissions.

Unit tests SHALL cover:

- manifest path resolution relative to manifest directory
- duplicate asset slide indexes fail
- missing listed files fail before renderer mutation
- missing slide assets use fallback visuals
- extra manifest assets do not create extra slides
- `scripts.add_image` escapes paths, sets geometry, and does not set object names
- `keynote.add_image` validates path and registers image object metadata
- renderer emits `keynote.add_image` for matching assets
- renderer appends image tool results to `RenderResult.tool_results`
- renderer uses full-bleed image geometry when assets are available
- renderer uses blank layout and skips default titles for image-backed slides 2..N
- renderer overlays text after image insertion
- renderer preserves no-image fallback behavior
- CLI `--images` validates and passes assets to renderer

Integration tests SHALL remain opt-in with:

```bash
RUN_KEYNOTE_INTEGRATION=1
```
