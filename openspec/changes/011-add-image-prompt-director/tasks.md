# Tasks: Add Image Prompt Director

## 1. Schema

- [x] Add `images/director.py`.
- [x] Define `DirectedImagePrompt` with Pydantic v2 and `extra="forbid"`.
- [x] Validate non-empty `slide_title`, `primary_scene`, and `prompt`.
- [x] Validate list fields contain only non-empty strings.
- [x] Add unit tests for valid and invalid `DirectedImagePrompt`.

## 2. Director

- [x] Implement `build_directed_image_prompt(deck, slide)`.
- [x] Derive `primary_scene` primarily from `slide.visual.description`.
- [x] Add scene-first prompt ordering.
- [x] Add fixed-preset style anchor before primary scene while keeping primary scene before story context.
- [x] Add `Required subjects` section when available.
- [x] Add `Composition` section when available.
- [x] Add `Style` section from DeckSpec / VisualSpec only.
- [x] Add `Story context` after primary scene and required subjects.
- [x] Add the no-text/no-watermark instruction.
- [x] Ensure prompt does not start with deck title.
- [x] Add tests for prompt ordering.

## 3. Required And Forbidden Subjects

- [x] Reuse or move existing emoji-to-English object mapping into director-safe helpers.
- [x] Extract conservative required subjects from visual description, emoji, title, subtitle, and body.
- [x] Build generic forbidden subjects for text, watermark, logo, document, poster, and UI.
- [x] Include `DeckSpec.style.avoid` terms in `negative_prompt`.
- [x] Add conservative drift exclusions without story-specific deck-title branches.
- [x] Ensure humans, children, animals, castles, forests, houses, and food are not globally forbidden.
- [x] Add tests for required subjects and forbidden subjects.

## 4. Style Modes

- [x] Ensure no fixed art styles are injected by the director.
- [x] Style notes come only from `deck.style.mood`, `audience`, `typography`, `palette`, and `visual.decorations`.
- [x] Add regression tests that absent user-provided style terms like watercolor, 3D, cinematic, soft lighting, and oil painting are not inserted.
- [x] Replace strict style neutrality with controlled style mode support.
- [x] Define supported style mode IDs: `soft_storybook_watercolor`, `cute_hand_drawn_cartoon`, `paper_cut_collage_storybook`, `deck_style`.
- [x] Use `soft_storybook_watercolor` as the default style mode.
- [x] Add preset descriptions to the provider-facing prompt and `DirectedImagePrompt.style_notes`.
- [x] Repeat fixed preset descriptions at the start of provider-facing prompts as `Image style, follow strongly`.
- [x] Ensure fixed preset modes do not automatically include `DeckSpec.style.mood`, `DeckSpec.style.typography`, `DeckSpec.style.palette`, or `SlideSpec.visual.decorations`.
- [x] Ensure `deck_style` mode uses DeckSpec / VisualSpec style fields as the primary style source.
- [x] Ensure `deck_style` mode does not include fixed preset descriptions.
- [x] Populate `ImageSpec.style` with the selected style mode ID so `art_spec.json` does not show the legacy `deck-specified` value.
- [x] Add style guardrails to `negative_prompt`: not photorealistic, not cinematic, not realistic portrait, not movie still, not 3D render, not adult editorial illustration.
- [x] Ensure no fixed art styles are injected outside the selected style mode.
- [x] Add tests for default style mode behavior, each supported fixed preset mode, `deck_style`, no hidden style mixing, artifact `style`, guardrails, and unknown style mode validation.

## 5. Planner Integration

- [x] Update `build_slide_art_specs(...)` to call `build_directed_image_prompt(...)`.
- [x] Populate `ImageSpec.prompt` from `DirectedImagePrompt.prompt`.
- [x] Populate `ImageSpec.negative_prompt` from `DirectedImagePrompt.negative_prompt`.
- [x] Preserve existing `SlideArtSpec` / `ImageSpec` schemas.
- [x] Preserve selected-slide behavior from 010.
- [x] Add tests that `build_slide_art_specs` uses scene-first directed prompts.
- [x] Add tests that fixed preset prompts start with style anchor and `deck_style` prompts remain scene-first.

## 6. Dry Run

- [x] Add a dry-run path for image prompt planning.
- [x] In dry-run, write `art_spec.json`.
- [x] In dry-run, do not call image provider.
- [x] In dry-run, do not require Bedrock/OpenAI credentials.
- [x] In dry-run, do not generate assets.
- [x] Decide and document whether `image_manifest.json` is omitted or empty; recommended: omit it. **Decision: omit — no assets exist.**
- [x] Add unit tests for dry-run generation behavior.

## 7. CLI

- [x] Add `oka generate-images --dry-run`.
- [x] Ensure `--dry-run` works with `--slides`.
- [x] Ensure `--dry-run` does not load or call real providers.
- [x] Print the `art_spec.json` path after dry-run.
- [x] Preserve existing non-dry-run CLI behavior.
- [x] Add CLI tests for `--dry-run`, `--dry-run --slides`, and provider-not-called behavior.
- [x] Add `oka generate-images --style <style-mode-id>`.
- [x] Make `--style` work in both dry-run and normal generation.
- [x] Validate unknown style mode IDs with a clear CLI error.
- [x] Add CLI tests for default style, explicit style, dry-run style, and invalid style.

## 8. Documentation

- [x] Update CLAUDE.md with 011 architecture notes.
- [x] Update README with prompt-review workflow.
- [x] Update AGENTS.md with 011 workflow note.
- [x] Update README with the three fixed style presets, `deck_style`, and preview workflow.
- [x] Update AGENTS.md / CLAUDE.md with the default style mode and `--style` option.
- [x] Update Chinese spec-reading notes for style mode behavior.

## 9. Quality Bar

- [x] Run `uv run pytest tests/test_images.py -q`.
- [x] Run `uv run pytest -q`.
- [x] Run `uv run ruff check .`.
