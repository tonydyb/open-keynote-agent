# Spec: Keynote Object Tools

## Purpose

Enable object-level Keynote editing so generated decks can include rich visual elements and support later user refinements.

## Requirements

### Helper Module

The system SHALL place object-related Python helpers in:

```text
src/open_keynote_agent/applescript/objects.py
```

This module SHALL own object ID validation/generation, object registry helpers, geometry validation, shape mapping, and color conversion.

`scripts.py` SHALL remain focused on AppleScript builders.

### Object IDs And Keynote References

The system SHALL assign a stable `object_id` to every object created by object tools.

The system SHALL accept caller-provided `object_id` values.

The system SHALL generate an `object_id` when one is not provided.

The system SHALL reject duplicate object IDs in the current session context.

The system SHALL validate object IDs with:

```text
^[a-z][a-z0-9_]{0,63}$
```

Generated object IDs SHALL use:

```text
slide_{slide:02d}_{kind}_{n}
```

where `kind` is one of `text_box`, `emoji`, or `shape`.

The system SHALL store generated-ID counters under `context["keynote"]["object_counters"]`.

The `object_id` SHALL be a local session identifier only.

The system SHALL NOT rely on Keynote `object name` or `name` properties for object naming or lookup. Real Keynote AppleScript does not expose a writable object-name property for `text item` and `shape` objects in this adapter.

After creating a Keynote object, the AppleScript builder SHALL return the created object's collection index by returning `count of text items` for text objects or `count of shapes` for shapes.

The handler SHALL parse that returned index and store `apple_class` and `apple_index` in the object registry. These fields are the Keynote-side reference used for later `move_object` and `resize_object`.

### Object Registry

The system SHALL track created objects in session context:

```json
{
  "keynote": {
    "objects": {
      "slide_08_the_end": {
        "object_id": "slide_08_the_end",
        "slide": 8,
        "type": "text_box",
        "apple_class": "text item",
        "apple_index": 3,
        "x": 360,
        "y": 260,
        "width": 560,
        "height": 110
      }
    },
    "slides": {
      "8": {
        "objects": ["slide_08_the_end"]
      }
    }
  }
}
```

Every object registry entry SHALL store at least `object_id`, `slide`, `type`, `apple_class`, `apple_index`, `x`, `y`, `width`, and `height`.

Text and emoji object entries SHALL store the rendered text under `text`.

Shape entries SHALL store the semantic shape under `shape`.

The system SHALL maintain `context["keynote"]["slides"]` as a required slide-to-object index.

Slide keys in `context["keynote"]["slides"]` SHALL be strings, e.g. `"8"`, not integers.

The system SHALL use this registry for later `move_object` and `resize_object` operations.

The system SHALL update object registry metadata only after the AppleScript runner returns success.

If an AppleScript runner call fails, the system SHALL NOT register a newly-created object and SHALL NOT mutate existing object metadata for move/resize.

### Geometry Validation

The system SHALL validate object geometry before running AppleScript:

- `slide >= 1`
- `x >= 0`
- `y >= 0`
- `width > 0`
- `height > 0`

Invalid geometry SHALL fail before calling the script runner.

If `context["keynote"]["slide_count"]` is known, the system SHALL reject `slide > slide_count` before calling the script runner.

### Text Box Tool

The system SHALL provide:

```text
keynote.add_text_box
```

with parameters:

```json
{
  "slide": 1,
  "text": "The End",
  "x": 360,
  "y": 260,
  "width": 560,
  "height": 110,
  "object_id": "slide_08_the_end",
  "font_size": 64,
  "font_color": "#6B3F1D"
}
```

The tool SHALL create a text object on the requested slide and record it in context. The tool SHALL NOT attempt to set Keynote `object name` or `name`.

The AppleScript builder SHALL create the text item without a properties record, then set `object text`, `position`, `width`, and `height` in separate statements.

The AppleScript builder SHALL return `count of text items`; the handler SHALL store that value as `apple_index` with `apple_class: "text item"`.

The AppleScript builder SHALL set font color, when provided, using:

```applescript
set text color of every paragraph of object text of textItem to {R, G, B}
```

The AppleScript builder SHALL NOT set `text color` directly on the text item object.

### Emoji Text Tool

The system SHALL provide:

```text
keynote.add_emoji_text
```

with parameters:

```json
{
  "slide": 3,
  "emoji": "🐷",
  "x": 760,
  "y": 180,
  "size": 96,
  "object_id": "slide_03_pig_emoji"
}
```

The tool SHALL create a text object containing the emoji and record it in context. The tool SHALL NOT attempt to set Keynote `object name` or `name`.

The `keynote.add_emoji_text` handler SHALL call `scripts.add_text_box(text=emoji, ...)` with emoji-specific defaults.

The system SHALL NOT add a separate `scripts.add_emoji_text()` builder in this change.

The system SHALL map emoji `size` to geometry using:

```text
width = size * 1.5
height = size * 1.5
font_size = size
```

The system SHALL reject `size <= 0` before running AppleScript.

The object registry entry for an emoji object SHALL store the mapped `width` and `height`.

### Shape Tool

The system SHALL provide:

```text
keynote.add_shape
```

with parameters:

```json
{
  "slide": 1,
  "shape": "rectangle",
  "x": 120,
  "y": 120,
  "width": 1000,
  "height": 420,
  "object_id": "slide_01_title_panel",
  "object_id": "slide_01_title_panel"
}
```

The MVP SHALL support:

```text
rectangle
```

The system SHALL NOT include `rounded_rectangle`, `oval`, or `line` in the MVP shape enum until a real Keynote AppleScript construction path is confirmed.

The system SHALL map shape names to Keynote AppleScript construction support:

| Semantic shape | AppleScript construction |
|---|---|
| `rectangle` | `make new shape` |

Unknown shapes SHALL fail before running AppleScript.

The AppleScript builder SHALL create shapes with this structure:

```applescript
set shapeItem to make new shape
set position of shapeItem to {<x>, <y>}
set width of shapeItem to <width>
set height of shapeItem to <height>
return count of shapes
```

The AppleScript builder SHALL NOT attempt to set Keynote `object name` or `name`.

The AppleScript builder SHALL return `count of shapes`; the handler SHALL store that value as `apple_index` with `apple_class: "shape"`.

If `fill_color` is provided, the tool SHALL fail before running AppleScript. Real Keynote AppleScript reports `background fill type` as read-only in this adapter, so valid shape fill support is deferred.

### Move Object Tool

The system SHALL provide:

```text
keynote.move_object
```

with parameters:

```json
{
  "object_id": "slide_08_the_end",
  "x": 320,
  "y": 240
}
```

The tool SHALL look up the object in context, move the Keynote object using the stored `apple_class` and `apple_index` on the recorded slide, and update context only after script success.

If the object ID is unknown, the tool SHALL fail before running AppleScript.

### Resize Object Tool

The system SHALL provide:

```text
keynote.resize_object
```

with parameters:

```json
{
  "object_id": "slide_08_the_end",
  "width": 660,
  "height": 140
}
```

The tool SHALL look up the object in context, resize the Keynote object using the stored `apple_class` and `apple_index` on the recorded slide, and update context only after script success.

If the object ID is unknown, the tool SHALL fail before running AppleScript.

### Colors

The system SHALL accept hex RGB colors such as:

```text
#F6A04D
```

Invalid colors SHALL fail before running AppleScript.

The system SHALL convert colors using:

```text
#RRGGBB -> {round(R * 65535 / 255), round(G * 65535 / 255), round(B * 65535 / 255)}
```

If a color argument is provided, the system SHALL either apply it to the generated Keynote object or fail before running AppleScript.

The system SHALL NOT silently ignore a valid color argument.

### Testing

Unit tests SHALL use `FakeScriptRunner`.

No unit test SHALL require Keynote, `osascript`, GUI access, or macOS Automation permissions.

Integration tests SHALL remain skipped unless `RUN_KEYNOTE_INTEGRATION=1` is set.

The integration smoke test SHALL reuse the 006 discovery setup: list themes, choose `Parchment` > `Basic White` > first returned theme, create document with that theme, list layouts, then add a `title_body` slide before exercising object tools.
