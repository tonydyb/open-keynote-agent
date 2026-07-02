# Spec: Readable Storybook Text Overlays

## Purpose

Improve readability of text overlays on image-backed storybook slides.

## Requirements

### Scope

The system SHALL improve the renderer's text overlay placement and styling for slides that have image assets.

The system SHALL NOT generate images.

The system SHALL NOT call an LLM.

The system SHALL NOT change `DeckSpec`.

The system SHALL preserve no-image rendering behavior.

The system SHALL preserve 012 full-bleed image behavior.

### Overlay Planning

The system SHALL add a deterministic overlay planner.

The planner SHALL accept:

```text
SlideSpec
image_path
```

The planner SHALL return an overlay plan containing:

```text
slide_index
text
region
text_color
font_size
backing recommendation
diagnostics
```

The planner SHALL be implemented in a pure/testable module, preferably:

```text
renderers/overlays.py
```

### Candidate Regions

The planner SHALL evaluate multiple deterministic candidate regions.

The planner SHALL include at least:

```text
bottom_band
top_band
left_panel
right_panel
```

The planner MAY include:

```text
center_caption
```

All coordinates SHALL use the existing 1280x720 coordinate system.

### Image Analysis

The planner SHALL inspect the image pixels under candidate regions when possible.

The planner SHALL compute mean luminance for each candidate region.

The planner SHOULD compute a busyness score such as luminance standard deviation.

If image analysis fails, the planner SHALL return a deterministic fallback plan rather than failing the entire render.

### Text Color

The planner SHALL choose text color based on sampled background luminance.

The default color rule SHALL be:

```text
dark background -> #FFFFFF
bright background -> #2C1810
```

The planner SHALL record luminance and chosen color in diagnostics.

### Backing / Contrast Support

The planner SHALL recommend a backing panel when the selected region is visually busy or luminance is ambiguous.

The planner SHALL expose this recommendation in the overlay plan.

The renderer SHOULD emit a backing object when the Keynote adapter supports the necessary shape/image operation safely.

If backing emission is not implemented, the renderer SHALL NOT fail; it SHALL still render text with the selected color.

### Shadow / Outline

The planner MAY recommend text shadow or outline.

The renderer SHALL NOT fail if shadow/outline cannot be emitted through Keynote AppleScript.

If shadow/outline is not emitted, diagnostics or tests SHOULD make that limitation explicit.

### Text Position

The planner SHALL choose the candidate region with the lowest deterministic score.

The score SHOULD prefer:

- lower busyness
- adequate contrast
- avoiding central subject-heavy areas where a simple heuristic is available
- slide-kind-specific preferred regions

The scoring algorithm SHALL be deterministic.

### Text Content

Overlay text SHALL be derived from the existing `SlideSpec`.

The renderer SHALL use:

1. `body`, when present
2. `subtitle`, when body is empty
3. `title`, when both body and subtitle are empty

For cover slides, the renderer MAY keep the default cover title and overlay only subtitle/body.

Overlay text SHALL NOT add bullet characters by default.

### Renderer Integration

For image-backed slides, the renderer SHALL insert objects in this order:

1. full-bleed slide image
2. optional backing support
3. overlay text box

The overlay text box SHALL use the planned region.

The overlay text box SHALL use the planned `text_color` through the existing `font_color` argument of `keynote.add_text_box`.

Slides without image assets SHALL keep the existing emoji/shape fallback behavior.

### CLI

The existing command SHALL continue to work:

```bash
oka render-storybook <deck_spec.json> --images <image_manifest.json>
```

Any new CLI options SHALL be optional.

If an overlay mode option is added, default mode SHALL be automatic image-aware planning.

### Testing

Unit tests SHALL NOT require real Keynote, `osascript`, GUI access, or macOS Automation permissions.

Unit tests SHALL cover:

- bright image region chooses dark text
- dark image region chooses white text
- busy or ambiguous image region recommends backing
- region scoring chooses a less busy candidate when available
- analysis failure falls back deterministically
- renderer emits overlay text after image insertion
- renderer passes planned font color to `keynote.add_text_box`
- no-image renderer behavior remains unchanged

Integration tests SHALL remain opt-in with:

```bash
RUN_KEYNOTE_INTEGRATION=1
```
