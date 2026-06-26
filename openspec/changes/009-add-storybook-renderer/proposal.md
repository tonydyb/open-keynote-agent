# Proposal: Add Storybook Renderer

## Summary

Add a deterministic storybook renderer that converts a validated `DeckSpec` into a Keynote deck using the built-in `Parchment` theme, simple童话绘本 layout templates, emoji visuals, and MVP rectangle decorations.

This change is the first full path from structured deck plan to real Keynote output:

```text
DeckSpec JSON -> storybook renderer -> keynote.* tools -> exported PDF
```

## Motivation

008 introduced `DeckSpec` as a safe planning artifact, but users still cannot turn that artifact into a visible presentation. The next step is a renderer that consumes the approved plan and calls deterministic Keynote tools.

The renderer should be intentionally conservative. It should generate useful, inspectable storybook-style decks without depending on unverified Keynote features such as image insertion, arbitrary shape types, shape fill colors, or GUI clicking.

## Goals

- Add a renderer that consumes `DeckSpec`.
- Create a Keynote document with the `Parchment` theme by default.
- Render each slide using deterministic storybook layout templates.
- Use `keynote.add_slide`, `keynote.set_slide_title`, `keynote.add_text_box`, `keynote.add_emoji_text`, and `keynote.add_shape`.
- Use emoji and simple rectangle decorations so every slide has visual elements.
- Export the rendered deck to PDF for inspection.
- Add a CLI command that renders from an existing `deck_spec.json`.
- Keep unit tests deterministic using `FakeScriptRunner`.
- Keep real Keynote smoke tests opt-in.

## Non-Goals

- Do not generate images in this change.
- Do not insert user-uploaded images.
- Do not implement arbitrary shape types beyond the current 007 MVP `rectangle`.
- Do not use shape fill color until 007 adds a confirmed writable fill path.
- Do not implement advanced typography, animation, tables, charts, or masks.
- Do not use Accessibility API or GUI clicking.
- Do not ask the LLM to create raw AppleScript.
- Do not modify the 008 DeckSpec schema unless a bug fix is required.

## User Story

Given a previously generated deck spec:

```bash
uv run oka deck-plan "请为我制作一个关于《三只小猪》的 8 页童话绘本风 Keynote" --slides 8 --output /tmp/three-pigs-plan
```

The user can render it:

```bash
uv run oka render-storybook /tmp/three-pigs-plan/deck_spec.json --output /tmp/three-pigs-rendered
```

The command creates a Keynote document, renders every DeckSpec slide, exports a PDF, and writes a render log for debugging.

## Success Criteria

- A valid `DeckSpec` can be rendered into a Keynote document.
- The renderer uses `Parchment` by default when available.
- The renderer creates one Keynote slide per `SlideSpec`.
- Each rendered slide includes title text, body text when present, and at least one visual element.
- The renderer uses deterministic layout templates rather than LLM-generated coordinates.
- Unit tests use fake runners and do not require Keynote.
- Integration tests remain opt-in with `RUN_KEYNOTE_INTEGRATION=1`.
