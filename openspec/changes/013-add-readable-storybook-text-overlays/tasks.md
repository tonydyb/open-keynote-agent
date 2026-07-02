# Tasks: Add Readable Storybook Text Overlays

## 1. Overlay Models

- [x] Add overlay planning models or dataclasses.
- [x] Include `OverlayRegion`, `OverlayStyle`, and `OverlayPlan`.
- [x] Keep models deterministic and serializable for diagnostics/tests.

## 2. Image Analysis

- [x] Add `renderers/overlays.py`.
- [x] Load image dimensions safely.
- [x] Map 1280x720 Keynote coordinates to image pixels.
- [x] Compute mean luminance for a candidate region.
- [x] Compute a basic busyness score.
- [x] Return deterministic fallback metrics when analysis fails.
- [x] Add tests for bright, dark, and busy synthetic images.

## 3. Text Color And Contrast

- [x] Choose `#FFFFFF` for dark backgrounds.
- [x] Choose `#2C1810` for bright backgrounds.
- [x] Mark ambiguous or busy regions as needing backing.
- [x] Add tests for threshold behavior.

## 4. Candidate Regions And Scoring

- [x] Define deterministic candidate regions: bottom, top, left, right.
- [x] Optionally add center caption.
- [x] Score regions by busyness, contrast, and slide-kind preference.
- [x] Select the lowest-score region.
- [x] Add tests that a less busy region is selected.

## 5. Renderer Integration

- [x] Replace or extend `calls_for_slide_text_only` with image-aware overlay planning.
- [x] Keep full-bleed `keynote.add_image` from 012.
- [x] Emit optional backing support only if safe with current Keynote tools.
- [x] Emit `keynote.add_text_box` after image insertion.
- [x] Pass planned `font_color` into `keynote.add_text_box`.
- [x] Preserve no-image fallback behavior.
- [x] Add tests that image insertion precedes overlay text.
- [x] Add tests that font color appears in generated text box calls.

## 6. Optional CLI

- [x] Decide whether to add `--overlay-mode`. (No new flag in MVP — auto is the only mode.)

## 7. Documentation

- [x] Update README with readable overlay behavior.
- [x] Update AGENTS.md and CLAUDE.md architecture notes.
- [x] Add/update Chinese spec-reading notes.
- [x] Document limitations: no LLM, no vision model, simple heuristics only.

## 8. Quality Bar

- [x] Run `uv run pytest tests/test_storybook_renderer.py tests/test_keynote_tools.py -q`.
- [x] Run `uv run pytest -q`.
- [x] Run `uv run ruff check .`.
- [ ] Optionally run `RUN_KEYNOTE_INTEGRATION=1 uv run pytest -m keynote_integration -s` on macOS with Keynote.
