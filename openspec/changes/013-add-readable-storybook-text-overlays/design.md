# Design: Add Readable Storybook Text Overlays

## Overview

013 adds an image-aware overlay planning layer between loaded image assets and Keynote tool calls.

The renderer remains deterministic:

```text
SlideSpec + image path
  -> analyze candidate regions with Pillow
  -> OverlayPlan
  -> Keynote calls:
       add_image full-bleed
       optional backing shape / shadow support
       add_text_box with selected font color and region
```

No LLM and no vision model are used.

## Modules

Add a new module:

```text
src/open_keynote_agent/renderers/overlays.py
```

It owns pure, testable overlay planning helpers.

## Data Models

Use Pydantic v2 models or dataclasses consistent with nearby renderer code:

```python
class OverlayRegion:
    name: str
    x: float
    y: float
    width: float
    height: float

class OverlayStyle:
    text_color: str
    font_size: float
    use_backing: bool
    backing_color: str | None
    backing_opacity: float | None
    shadow: bool

class OverlayPlan:
    slide_index: int
    region: OverlayRegion
    style: OverlayStyle
    text: str
    diagnostics: dict[str, float | str | bool]
```

`text_color`, `backing_color` use `#RRGGBB`.

`backing_opacity` is `0.0..1.0`.

## Candidate Regions

Define several deterministic candidate regions in the existing 1280x720 coordinate system:

```text
bottom_band
top_band
left_panel
right_panel
center_caption
```

Recommended initial constants:

```text
bottom_band:  x=90,  y=500, width=1100, height=170
top_band:     x=90,  y=50,  width=1100, height=150
left_panel:   x=70,  y=120, width=430,  height=480
right_panel:  x=780, y=120, width=430,  height=480
center_caption: x=190, y=430, width=900, height=190
```

The implementation may tune exact values, but tests should assert stable output.

## Image Analysis

Use Pillow. If Pillow is not available, fall back to the existing 012 deterministic overlay region.

For each candidate region:

1. Map Keynote point coordinates to image pixel coordinates.
2. Crop the region.
3. Compute:
   - mean luminance
   - luminance standard deviation
   - edge/busyness score
   - optional center-subject penalty

Luminance formula:

```text
Y = 0.2126 * R + 0.7152 * G + 0.0722 * B
```

Busyness can start with the standard deviation of luminance. A later implementation may add gradient/edge detection.

## Text Color Selection

Choose:

```text
mean_luminance < 128 -> #FFFFFF
mean_luminance >= 128 -> #2C1810
```

Use hysteresis or contrast thresholds if needed:

- If luminance is near the threshold (`112..144`) or busyness is high, enable backing.
- If contrast against both colors is weak, enable backing.

## Backing Panel

If region busyness is above a threshold or luminance is ambiguous, add a semi-transparent backing panel.

Because current `keynote.add_shape` does not support fill color/opacity reliably, the first implementation has two acceptable options:

1. Add renderer-level support for a simple backing shape only if the existing Keynote adapter can express it safely.
2. If Keynote backing shape is not reliable yet, emit no backing object but include `use_backing=True` in `OverlayPlan.diagnostics` and keep text color selection. This keeps the planning contract ready for a later Keynote shape enhancement.

Preferred future direction: generate a small translucent PNG backing panel and insert it before the text using `keynote.add_image`.

## Shadow / Outline

Text shadow/outline is desirable but AppleScript support may be limited.

MVP behavior:

- `OverlayStyle.shadow` may be planned.
- If Keynote text shadow is not implemented, do not fail; omit the shadow tool call.
- The plan must record whether shadow was requested and whether it was emitted.

## Template Selection

Score each candidate region.

Example scoring:

```text
score =
  busyness * 1.0
  + center_subject_penalty * 0.7
  + edge_penalty * 0.3
  + preferred_region_penalty
```

Lower score wins.

Default preferences:

- `cover`: prefer `bottom_band` unless subtitle is short, then `center_caption` is allowed
- `characters`: prefer `bottom_band` or `top_band`
- `chapter/content`: prefer `bottom_band`
- `climax`: prefer `top_band` if bottom is busy
- `lesson`: prefer `left_panel` or `right_panel`
- `ending`: prefer `bottom_band` or `center_caption`

These are deterministic preferences, not LLM decisions.

## Text Extraction

Reuse 012 rules:

- cover: subtitle/body overlay if present; cover title may remain default
- slides 2..N: `SlideSpec.body` first
- if body empty, use subtitle
- if subtitle empty, use title

Do not add bullet marks for image-backed overlay text.

## Renderer Integration

Update `calls_for_slide_text_only(...)` or replace it with:

```python
calls_for_slide_image_overlay(slide, image_path) -> list[ProposedToolCall]
```

Renderer order remains:

1. `keynote.add_image` full-bleed illustration
2. optional backing support
3. `keynote.add_text_box` overlay text

The text box SHALL use the selected `text_color` as `font_color`.

If analysis fails, the renderer SHALL fall back to 012's fixed overlay frame and deterministic default color.

## CLI

No new required CLI option.

Optional flags may be added:

```text
--overlay-mode auto|bottom|top|left|right
--no-overlay-backing
```

If flags are added, default behavior SHALL be `auto`.

## Testing

Tests should create small synthetic PNGs with Pillow or stdlib PNG fixtures if feasible.

Required tests:

- bright region chooses dark text
- dark region chooses white text
- busy/ambiguous region requests backing
- candidate selection picks the lower-busyness region
- missing/unreadable image falls back to 012 overlay
- renderer emits text after image
- renderer passes `font_color` to `keynote.add_text_box`
- no-image fallback is unchanged

## Risks

- Simple luminance analysis cannot truly understand faces or subjects.
- Generated images may put important subjects in all candidate regions.
- Keynote AppleScript may not expose reliable fill/opacity/shadow controls.

The design intentionally keeps the first version conservative and deterministic.
