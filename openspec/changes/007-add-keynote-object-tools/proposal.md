# Proposal: Add Keynote Object Tools

## Summary

Add object-level Keynote tools for creating and manipulating text boxes, emoji text, and simple shapes. Introduce deterministic local object IDs so generated decks can be refined after creation.

This change is the bridge between basic slide creation and a real deck renderer. It enables future storybook layouts to place visual elements on each slide and lets users make follow-up edits such as “add The End on the last slide” or “move the wolf emoji to the right.”

## Motivation

The current Keynote adapter can create documents, add slides, set default title/body text, and export PDFs. That is enough for smoke tests, but not enough for visually rich decks.

The “Three Little Pigs” target requires:

- large decorative text
- emoji visuals
- colored geometric shapes
- object placement
- object resizing
- stable local object IDs for later refinement

Keynote object tools should remain deterministic and local. The LLM should choose registered tools and arguments; local code should validate positions, sizes, names, and styles before generating AppleScript.

## Goals

- Add `keynote.add_text_box`.
- Add `keynote.add_emoji_text`.
- Add `keynote.add_shape`.
- Add `keynote.move_object`.
- Add `keynote.resize_object`.
- Add deterministic local object ID conventions.
- Track created objects in `context["keynote"]["slides"][slide]["objects"]`.
- Keep tests deterministic using `FakeScriptRunner`.
- Keep existing `demo.*` tools and existing Keynote tools working.

## Non-Goals

- Do not implement image insertion yet.
- Do not implement full deck rendering yet.
- Do not implement advanced typography, animations, tables, charts, or image masks.
- Do not use Accessibility API or GUI clicking.
- Do not rely on reading every object property back from Keynote in this change.
- Do not allow arbitrary AppleScript from the LLM.

## User Stories

- As a user, I can ask the agent to add a large `The End` text box on the final slide.
- As a user, I can ask the agent to add pig and wolf emoji as visual elements.
- As a user, I can ask the agent to move or resize an object that was created earlier.
- As a developer, I can generate predictable object IDs and use them in later tool calls.
- As a developer, I can test all object tools without launching Keynote.

## Example

```text
oka> Add a big The End text in the center of slide 8.

Plan:
  1. keynote.add_text_box object_id=slide_08_the_end slide=8 text="The End" x=360 y=260 width=560 height=110 font_size=64
Apply? [y/N]
```

Later:

```text
oka> Make The End bigger.

Plan:
  1. keynote.resize_object object_id=slide_08_the_end width=660 height=140
Apply? [y/N]
```

## Success Criteria

- Existing tests pass.
- New object tools are registered under `keynote.*`.
- All object tools validate coordinates and dimensions before running AppleScript.
- Created objects receive stable `object_id` values.
- Created objects are recorded in session context.
- Move/resize can target objects by `object_id`.
- Unit tests use `FakeScriptRunner` and never require Keynote.
- Integration tests remain opt-in with `RUN_KEYNOTE_INTEGRATION=1`.
