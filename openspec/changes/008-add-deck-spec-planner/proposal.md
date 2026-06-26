# Proposal: Add Deck Spec Planner

## Summary

Add a deck-spec planning layer that converts a long natural-language presentation brief into validated `DeckSpec` JSON and a readable slide outline.

This change does not render Keynote slides yet. It creates the structured design plan that future renderers and refinement workflows will consume.

## Motivation

The current `oka session` flow can plan individual tool calls, but a request such as “create an 8-slide storybook Keynote about The Three Little Pigs” is too large to safely execute as ad-hoc tool calls.

Before rendering, the system needs a stable intermediate artifact:

```text
User brief -> DeckSpec JSON -> validated outline -> future renderer
```

This gives the user and agent a chance to inspect, validate, revise, and approve the deck plan before mutating Keynote.

## Goals

- Define `DeckSpec`, `SlideSpec`, `StyleSpec`, `VisualSpec`, and related Pydantic v2 models.
- Add an LLM-backed planner that converts a long prompt into validated `DeckSpec` JSON.
- Generate a human-readable slide outline from `DeckSpec`.
- Persist `deck_spec.json` and `outline.md` under `.runs/<run-id>/`.
- Add tests using `FakeLLMClient`.
- Keep tests independent of cloud credentials and Keynote.

## Non-Goals

- Do not render Keynote slides in this change.
- Do not add image generation.
- Do not add frontend GUI.
- Do not add multimodal image input.
- Do not execute `keynote.*` tools from `DeckSpec` yet.
- Do not replace the existing `oka session` runtime.
- Do not model renderer-only object geometry in this change.

## User Story

User prompt:

```text
请为我制作一个关于《三只小猪》故事的精美 Keynote 演示文稿...
```

Planner output:

```text
Deck: 三只小猪与大灰狼
Theme: Parchment
Style: 童话绘本风 / 暖色调 / 儿童友好

1. 封面 — 三只小猪与大灰狼
2. 角色介绍 — 大毛、二毛、小毛
3. 第一章 — 大毛的稻草屋
...
8. The End — 故事启示
```

The next change can take this `DeckSpec` and render it using deterministic Keynote layout templates.

## Success Criteria

- A long user prompt can be converted into a validated `DeckSpec`.
- The generated spec contains 7-8 slides for the Three Little Pigs example.
- The system emits a readable outline.
- Invalid LLM output is rejected with clear validation errors.
- Unit tests use `FakeLLMClient`.
- No test requires Keynote, `osascript`, cloud credentials, or API keys.
