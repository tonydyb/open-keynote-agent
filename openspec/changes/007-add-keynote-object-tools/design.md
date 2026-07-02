# Design: Keynote Object Tools

## Overview

This change adds object-level Keynote tools on top of the AppleScript adapter. These tools are needed for deterministic layout templates and user refinement.

```text
DeckSpec / user refinement
  -> keynote.add_text_box
  -> keynote.add_emoji_text
  -> keynote.add_shape
  -> keynote.move_object
  -> keynote.resize_object
  -> context object registry
```

The implementation remains AppleScript-backed and testable through `FakeScriptRunner`.

## Coordinate System

Use Keynote point coordinates with a top-left origin:

```text
x: left position
y: top position
width: object width
height: object height
```

All geometry values are numbers. Tools must validate:

- `slide >= 1`
- `x >= 0`
- `y >= 0`
- `width > 0`
- `height > 0`

If `context["keynote"]["slide_count"]` is known, tools must also validate `slide <= slide_count` before running AppleScript. If the slide count is absent, tools may rely on Keynote to report a script error.

The MVP assumes wide 16:9 slides. Future changes may add slide-size discovery and responsive layout scaling.

## Object IDs

Every created object must have a stable `object_id`.

Object-related Python helpers live in:

```text
src/open_keynote_agent/applescript/objects.py
```

This module owns object ID validation/generation, context registry helpers, geometry validation, shape mapping, and color conversion. `scripts.py` remains focused on AppleScript string builders.

Rules:

- Caller may provide `object_id`.
- If omitted, the handler generates one from tool type, slide number, and a counter.
- IDs must be safe for context keys.
- IDs should use lowercase snake case where possible.
- Duplicate IDs in the same session context are rejected.

Validation:

```text
^[a-z][a-z0-9_]{0,63}$
```

Generated IDs use:

```text
slide_{slide:02d}_{kind}_{n}
```

Where `kind` is one of `text_box`, `emoji`, or `shape`, and `n` is a per-kind, per-slide counter stored under:

```json
context["keynote"]["object_counters"]
```

Examples:

```text
slide_01_title_label
slide_02_pig_emoji_1
slide_08_the_end
```

`object_id` is a local session identifier only. Real Keynote AppleScript does not expose a writable `object name` or `name` property for the text and shape objects used in this adapter, so the implementation must not rely on Keynote-side names.

Creation scripts return the created object's collection index (`count of text items` or `count of shapes`). Handlers store that index as `apple_index` along with an `apple_class` such as `text item` or `shape`. Later move/resize scripts use the stored `(slide, apple_class, apple_index)` reference.

## Context Object Registry

Extend `context["keynote"]` with slide/object metadata:

```json
{
  "keynote": {
    "slide_count": 8,
    "objects": {
      "slide_08_the_end": {
        "object_id": "slide_08_the_end",
        "slide": 8,
        "type": "text_box",
        "apple_class": "text item",
        "apple_index": 3,
        "text": "The End",
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

Object entries must store at least:

```text
object_id
slide
type
apple_class
apple_index
x
y
width
height
```

Text and emoji entries also store the rendered text under `text`. Shape entries store `shape`.

The `slides` sub-registry is required. It is an index for future “list objects on slide” and renderer cleanup workflows. Slide keys are strings, not integers, because session context is serialized as JSON:

```json
context["keynote"]["slides"]["8"]["objects"]
```

This registry is the authoritative local reference for refinement. It is a best-effort mirror of Keynote state; if a user edits the Keynote manually outside the agent, the stored AppleScript indexes may become stale.

Context updates are success-only:

1. Validate all local arguments.
2. Build and run AppleScript.
3. If `result.ok` is false, raise an error and leave object registry metadata unchanged.
4. If `result.ok` is true, update `context["keynote"]["objects"]`, `context["keynote"]["slides"]`, and any object counters.

## AppleScript Builders

Add builders in `applescript/scripts.py`:

```python
def add_text_box(
    slide: int,
    object_id: str,
    text: str,
    x: float,
    y: float,
    width: float,
    height: float,
    font_size: float | None = None,
    font_color: str | None = None,
) -> str: ...

def add_shape(
    slide: int,
    object_id: str,
    shape: str,
    x: float,
    y: float,
    width: float,
    height: float,
    fill_color: str | None = None,
) -> str: ...

def move_object(slide: int, apple_class: str, apple_index: int, x: float, y: float) -> str: ...
def resize_object(slide: int, apple_class: str, apple_index: int, width: float, height: float) -> str: ...
```

There is no separate `scripts.add_emoji_text()` builder in this change. The `keynote.add_emoji_text` handler must call `scripts.add_text_box(text=emoji, ...)` with emoji-specific defaults.

All string values must use `applescript_string` before interpolation.

`add_text_box` must follow this AppleScript shape:

```applescript
tell application "Keynote"
  tell front document
    tell slide <slide>
      set textItem to make new text item
      set object text of textItem to "<text>"
      set position of textItem to {<x>, <y>}
      set width of textItem to <width>
      set height of textItem to <height>
      if <font_size provided> then
        set size of every paragraph of object text of textItem to <font_size>
      end if
      if <font_color provided> then
        set color of object text of textItem to {<r>, <g>, <b>}
      end if
      return count of text items
    end tell
  end tell
end tell
```

This rich-text color form is required; builders must not attempt to set `text color` directly on the text item object or paragraph range.

Move/resize builders must target the stored AppleScript class/index on a specific slide. Required lookup pattern:

```applescript
tell slide <slide>
  set targetItem to <apple_class> <apple_index>
  -- mutate targetItem
end tell
```

Builders must not use Keynote `object name` or `name` for object naming or lookup.

## Supported Shapes

MVP shape enum:

```text
rectangle
```

`rounded_rectangle`, `oval`, and `line` are intentionally out of scope until a real Keynote AppleScript construction path is confirmed. The current Keynote scripting dictionary does not expose a writable `shape type` property for `shape` objects in this adapter.

Handlers map semantic values to Keynote AppleScript construction support:

| Semantic shape | AppleScript construction |
|---|---|
| `rectangle` | `make new shape` |

If a shape is unsupported, raise `ValueError` before calling the runner.

## Colors

Use hex RGB strings in tool args:

```text
#F6A04D
#6B3F1D
```

Add a helper:

```python
hex_to_rgb_tuple("#F6A04D") -> tuple[int, int, int]
```

AppleScript builders must convert this into Keynote-compatible RGB color lists:

```applescript
{63000, 41000, 19000}
```

Conversion rule:

```text
#RRGGBB -> {round(R * 65535 / 255), round(G * 65535 / 255), round(B * 65535 / 255)}
```

The implementation must either apply provided colors to the generated object or reject invalid/unsupported color arguments before running AppleScript. It must not silently accept a color argument and ignore it.

## Tools

### `keynote.add_text_box`

Parameters:

```json
{
  "slide": 8,
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

Mutating: yes.

Creates a text item on the slide, sets text, position, size, and basic text styling, then stores a local object registry entry with the returned `apple_index`.

### `keynote.add_emoji_text`

Parameters:

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

Mutating: yes.

Creates a large text item containing emoji. It uses the shared `scripts.add_text_box(...)` builder.

Canonical size mapping:

```text
width = size * 1.5
height = size * 1.5
font_size = size
```

The mapped `width` and `height` values are the values stored in the object registry. `size` must be greater than 0.

### `keynote.add_shape`

Parameters:

```json
{
  "slide": 1,
  "shape": "rectangle",
  "x": 120,
  "y": 120,
  "width": 1000,
  "height": 420,
  "object_id": "slide_01_title_panel"
}
```

Mutating: yes.

Creates a simple default Keynote shape. This MVP supports `rectangle` only.

`add_shape` must follow this AppleScript shape:

```applescript
tell application "Keynote"
  tell front document
    tell slide <slide>
      set shapeItem to make new shape
      set position of shapeItem to {<x>, <y>}
      set width of shapeItem to <width>
      set height of shapeItem to <height>
      return count of shapes
    end tell
  end tell
end tell
```

If `fill_color` is provided, the handler must reject it before calling the runner. Real Keynote AppleScript reports the tested fill properties as read-only in this adapter.

### `keynote.move_object`

Parameters:

```json
{
  "object_id": "slide_08_the_end",
  "x": 320,
  "y": 240
}
```

Mutating: yes.

Looks up the object in context to find its slide and stored `(apple_class, apple_index)`, generates AppleScript to move that object, and updates context only after script success.

### `keynote.resize_object`

Parameters:

```json
{
  "object_id": "slide_08_the_end",
  "width": 660,
  "height": 140
}
```

Mutating: yes.

Looks up the object in context to find its slide and stored `(apple_class, apple_index)`, generates AppleScript to resize that object, and updates context only after script success.

## Registration

`register_keynote_tools()` should register the new object tools alongside existing Keynote tools. Existing tool names and behavior must remain compatible.

## Error Handling

Handlers must fail before AppleScript execution when:

- geometry is invalid
- shape enum is unknown
- color format is invalid
- `object_id` is invalid
- `object_id` already exists for create tools
- `object_id` does not exist for move/resize tools

Script failures still follow the existing pattern:

```text
RuntimeError(result.stderr or "AppleScript error")
```

The executor converts these into failed `ToolResult`s.

## Testing Strategy

Unit tests use `FakeScriptRunner`.

Cover:

- object ID generation
- duplicate object ID rejection
- invalid geometry rejection before runner call
- invalid color rejection before runner call
- `add_text_box` sends expected AppleScript and updates context
- `add_emoji_text` sends expected AppleScript and updates context
- `add_shape` sends expected AppleScript and updates context
- `move_object` looks up context and updates position
- `resize_object` looks up context and updates dimensions
- runner failures become failed `ToolResult`

Integration tests remain opt-in:

```bash
RUN_KEYNOTE_INTEGRATION=1
```

Smoke test:

1. Reuse the 006 discovery setup: list themes.
2. Choose `Parchment` if present, otherwise `Basic White` if present, otherwise the first returned theme.
3. Create document with the selected theme.
4. List layouts.
5. Add a `title_body` slide through semantic layout resolution.
6. Add `The End` text box.
7. Add emoji visual.
8. Add the MVP decorative shape: `rectangle`.
9. Move or resize one object.
10. Export PDF.

## Safety

- No raw AppleScript from the LLM.
- All string interpolation is escaped.
- Mutating object tools require the existing approval flow.
- Tools validate local arguments before calling `osascript`.
