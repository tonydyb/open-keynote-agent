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

## 4. Style Neutrality

- [x] Ensure no fixed art styles are injected by the director.
- [x] Style notes come only from `deck.style.mood`, `audience`, `typography`, `palette`, and `visual.decorations`.
- [x] Add regression tests that absent user-provided style terms like watercolor, 3D, cinematic, soft lighting, and oil painting are not inserted.

## 5. Planner Integration

- [x] Update `build_slide_art_specs(...)` to call `build_directed_image_prompt(...)`.
- [x] Populate `ImageSpec.prompt` from `DirectedImagePrompt.prompt`.
- [x] Populate `ImageSpec.negative_prompt` from `DirectedImagePrompt.negative_prompt`.
- [x] Preserve existing `SlideArtSpec` / `ImageSpec` schemas.
- [x] Preserve selected-slide behavior from 010.
- [x] Add tests that `build_slide_art_specs` uses scene-first directed prompts.

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

## 8. Documentation

- [x] Update CLAUDE.md with 011 architecture notes.
- [x] Update README with prompt-review workflow.
- [x] Update AGENTS.md with 011 workflow note.

## 9. Quality Bar

- [x] Run `uv run pytest tests/test_images.py -q`.
- [x] Run `uv run pytest -q`.
- [x] Run `uv run ruff check .`.
