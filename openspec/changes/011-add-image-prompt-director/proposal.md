# Proposal: Add Image Prompt Director

## Summary

Add a deterministic image prompt director that turns each `SlideSpec` into a more explicit, scene-focused image prompt plan before image generation.

This change improves illustration accuracy without changing image providers, Keynote rendering, or the DeckSpec planner.

```text
DeckSpec
  -> DirectedImagePrompt / SlideArtSpec
  -> art_spec.json
  -> existing 010 image generation pipeline
```

## Motivation

010 can generate high-quality images, but real image models often ignore slide-specific visual descriptions when the story title has strong visual priors. For example, a "Snow White" slide about the evil queen and magic mirror may produce Snow White, apples, dwarfs, or dining scenes because the prompt does not strongly separate the current scene from general story context.

The current prompt is good enough for plumbing, but not yet good enough for storybook production. The system needs a deterministic prompt-directing layer that:

- prioritizes the current slide's scene over generic story associations
- states required subjects explicitly
- states forbidden subjects explicitly
- pushes story title into background context
- makes `art_spec.json` easier to review before spending image-generation cost

## Goals

- Define a structured `DirectedImagePrompt` model.
- Compile each slide into a scene-first image prompt.
- Add required-subject and forbidden-subject sections.
- Add per-slide negative prompts that reduce common model drift.
- Add controlled children's-book illustration style modes, defaulting to `soft_storybook_watercolor`.
- Allow preview-time style selection from a small deterministic list, including `deck_style` for using the user's prompt-derived DeckSpec style.
- Keep the compiler deterministic and local.
- Add a prompt-only mode so users can review `art_spec.json` without calling an image provider.
- Preserve existing 010 CLI behavior when new options are not used.
- Keep tests independent of real image APIs, Keynote, and network access.

## Non-Goals

- Do not call an LLM in this change.
- Do not translate localized DeckSpecs.
- Do not add or change image providers.
- Do not change Bedrock request/response logic.
- Do not insert images into Keynote, PPTX, or PDF.
- Do not solve full cross-slide character identity consistency.
- Do not perform visual QA on generated images.
- Do not add frontend GUI.

## User Story

Given an English image-generation source deck:

```bash
uv run oka deck-plan "Create an 18-page Snow White storybook..." \
  --slides 18 \
  --output /tmp/snow-white-plan
```

Plan image prompts without generating images:

```bash
uv run oka generate-images /tmp/snow-white-plan/deck_spec_en.json \
  --slides 1,4,9 \
  --style soft_storybook_watercolor \
  --dry-run \
  --output /tmp/snow-white-prompts
```

The command writes:

```text
/tmp/snow-white-prompts/
  art_spec.json
```

Then generate only the reviewed slides:

```bash
uv run oka generate-images /tmp/snow-white-plan/deck_spec_en.json \
  --provider bedrock \
  --slides 1,4,9 \
  --style cute_hand_drawn_cartoon \
  --output /tmp/snow-white-preview
```

## Success Criteria

- `art_spec.json` contains scene-first prompts where the current slide description appears before story context.
- Prompts include explicit "Required subjects" and "Forbidden subjects" sections.
- Negative prompts include both generic exclusions and per-slide forbidden subjects.
- `soft_storybook_watercolor` is used as the default image style mode.
- Users can choose `soft_storybook_watercolor`, `cute_hand_drawn_cartoon`, `paper_cut_collage_storybook`, or `deck_style` during preview and generation.
- Fixed preset modes do not silently mix in `DeckSpec.style.mood`; `deck_style` is the explicit option for using DeckSpec / VisualSpec style fields.
- `--dry-run` writes `art_spec.json` and does not call the provider.
- Existing `oka generate-images` behavior remains compatible when `--dry-run` and new director options are not used.
- Unit tests prove no LLM, no real image API, and no Keynote dependency.
