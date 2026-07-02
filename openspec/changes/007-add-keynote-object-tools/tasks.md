# Tasks

## 1. Object Utilities

- [x] Add `src/open_keynote_agent/applescript/objects.py`.
- [x] Add object ID validation helper.
- [x] Add deterministic object ID generation helper.
- [x] Use object ID regex `^[a-z][a-z0-9_]{0,63}$`.
- [x] Generate IDs as `slide_{slide:02d}_{kind}_{n}`.
- [x] Store generated-ID counters under `context["keynote"]["object_counters"]`.
- [x] Add duplicate object ID detection.
- [x] Add object registry helpers for `context["keynote"]["objects"]`.
- [x] Add slide object list helpers for `context["keynote"]["slides"]`.
- [x] Add geometry validation helper.
- [x] Validate `slide <= context["keynote"]["slide_count"]` when slide count is known.
- [x] Add hex color validation/conversion helper.
- [x] Convert `#RRGGBB` to Keynote RGB lists using 0..65535 channel values.
- [x] Add semantic shape mapping helper for MVP `rectangle`.
- [x] Keep object utilities out of `scripts.py`; `scripts.py` should remain AppleScript builders only.
- [x] Add unit tests for all helpers.

## 2. AppleScript Builders

- [x] Add `scripts.add_text_box(...)`.
- [x] Do not add `scripts.add_emoji_text(...)`; `keynote.add_emoji_text` must call `scripts.add_text_box(text=emoji, ...)`.
- [x] Add `scripts.add_shape(...)`.
- [x] Add `scripts.move_object(...)`.
- [x] Add `scripts.resize_object(...)`.
- [x] In `scripts.add_text_box(...)`, set font color with `set color of object text of textItem to {R, G, B}`.
- [x] Do not set `text color` directly on the text item object or paragraph range.
- [x] In `scripts.add_shape(...)`, create the MVP default shape with `make new shape`.
- [x] Reject `fill_color` before runner call until a writable Keynote fill path is confirmed.
- [x] Treat `object_id` as a local session ID only.
- [x] Store created Keynote references as `apple_class` and `apple_index`.
- [x] Use stored `apple_class`/`apple_index` on the recorded slide for move/resize.
- [x] Do not use Keynote `object name` or `name` for object naming or lookup.
- [x] Ensure all string interpolation uses `applescript_string`.
- [x] Apply provided `font_color` / `fill_color` arguments in AppleScript or reject them before runner call.
- [x] Add unit tests for generated AppleScript.

## 3. Keynote Tools

- [x] Add `keynote.add_text_box`.
- [x] Add `keynote.add_emoji_text`.
- [x] Implement `keynote.add_emoji_text` size mapping as `width=size*1.5`, `height=size*1.5`, `font_size=size`.
- [x] Reject `keynote.add_emoji_text` when `size <= 0` before runner call.
- [x] Add `keynote.add_shape`.
- [x] Add `keynote.move_object`.
- [x] Add `keynote.resize_object`.
- [x] Register new tools in `register_keynote_tools`.
- [x] Preserve all existing Keynote tools.
- [x] Keep `rounded_rectangle`, `oval`, and `line` out of the MVP shape enum until real AppleScript support is confirmed.

## 4. Context Updates

- [x] Record created text boxes in `context["keynote"]["objects"]`.
- [x] Record created emoji text objects in `context["keynote"]["objects"]`.
- [x] Record created shapes in `context["keynote"]["objects"]`.
- [x] Store `x`, `y`, `width`, and `height` on every object registry entry at creation time.
- [x] Store `apple_class` and `apple_index` on every object registry entry at creation time.
- [x] Store rendered `text` for text box and emoji objects.
- [x] Store semantic `shape` for shape objects.
- [x] Maintain required `context["keynote"]["slides"]` index.
- [x] Use string slide keys in `context["keynote"]["slides"]`, e.g. `"8"`, not integer keys.
- [x] Record object IDs under the owning slide string key.
- [x] Update object position after move.
- [x] Update object size after resize.
- [x] Update context only after the AppleScript runner returns success.
- [x] Do not register new objects after script failure.
- [x] Do not mutate existing object metadata after move/resize script failure.
- [x] Add unit tests for context updates.

## 5. Validation and Error Cases

- [x] Reject invalid slide indexes before runner call.
- [x] Reject slide numbers above known `slide_count` before runner call.
- [x] Reject invalid geometry before runner call.
- [x] Reject invalid shape enum before runner call.
- [x] Reject invalid color before runner call.
- [x] Reject duplicate object IDs before runner call.
- [x] Reject unknown object IDs for move/resize before runner call.
- [x] Reject valid-but-unsupported color styling before runner call rather than silently ignoring it.
- [x] Add unit tests proving runner is not called for validation failures.
- [x] Add unit tests proving context is unchanged after runner failures.

## 6. Integration Smoke Test

- [x] Reuse the 006 setup: list themes.
- [x] Select `Parchment` if present, else `Basic White` if present, else the first returned theme.
- [x] Create document with selected theme.
- [x] List layouts.
- [x] Add a `title_body` slide through semantic layout resolution.
- [x] Add a text box. (verified with RUN_KEYNOTE_INTEGRATION=1)
- [x] Add an emoji text object. (verified with RUN_KEYNOTE_INTEGRATION=1)
- [x] Add the MVP decorative shape: `rectangle`. (verified with RUN_KEYNOTE_INTEGRATION=1)
- [x] Move or resize one object. (verified with RUN_KEYNOTE_INTEGRATION=1)
- [x] Export PDF and assert it exists. (verified with RUN_KEYNOTE_INTEGRATION=1)

## 7. Documentation

- [x] Update README with object tool examples.
- [x] Update CLAUDE.md and AGENTS.md with local object ID and refinement guidance.
- [x] Document that object context is a best-effort local mirror and may become stale if the user manually edits Keynote.

## 8. Quality Bar

- [x] Run `uv run pytest`.
- [x] Run `uv run ruff check .`.
- [x] Confirm non-integration tests do not require Keynote or macOS Automation permissions.
