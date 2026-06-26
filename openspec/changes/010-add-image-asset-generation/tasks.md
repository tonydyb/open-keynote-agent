# Tasks

## 1. Image Package

- [ ] Add `src/open_keynote_agent/images/__init__.py`.
- [ ] Add `src/open_keynote_agent/images/schema.py`.
- [ ] Add `src/open_keynote_agent/images/planner.py`.
- [ ] Add `src/open_keynote_agent/images/provider.py`.
- [ ] Add `src/open_keynote_agent/images/generator.py`.
- [ ] Ensure image package does not import Keynote tools or AppleScript modules.

## 2. Models

- [ ] Define `ImageSpec`.
- [ ] Define `SlideArtSpec`.
- [ ] Define `ImageAsset`.
- [ ] Define `ImageManifest`.
- [ ] Use Pydantic v2 with `extra="forbid"`.
- [ ] Validate non-empty image prompt.
- [ ] Validate `aspect_ratio="16:9"`.
- [ ] Validate `output_format="png"`.
- [ ] Validate `slide_index >= 1`.
- [ ] Validate `asset_filename == slide_{index:02d}.png`.
- [ ] Add unit tests for valid and invalid models.

## 3. Art Spec Planner

- [ ] Implement `build_slide_art_specs(deck)`.
- [ ] Produce one `SlideArtSpec` per DeckSpec slide.
- [ ] Include deck title in prompts.
- [ ] Include style mood and audience in prompts.
- [ ] Include slide title, subtitle, and body in prompts.
- [ ] Include visual description, emoji, and decorations in prompts.
- [ ] Include "no text, no captions, no letters, no watermark" instruction.
- [ ] Keep prompt construction deterministic.
- [ ] Add unit tests for prompt contents and deterministic output.

## 4. Image Provider

- [ ] Define `ImageProvider` protocol.
- [ ] Define `ImageGenerationResult` if useful.
- [ ] Implement `FakeImageProvider`.
- [ ] Ensure fake provider writes valid PNG bytes.
- [ ] Add provider loader using `OKA_IMAGE_PROVIDER` with default `fake`.
- [ ] Add clear error for unknown or unconfigured providers.
- [ ] Optionally implement one real provider behind configuration.
- [ ] Ensure tests never call real provider.

## 5. Generation And Cache

- [ ] Implement prompt hash from canonical ImageSpec JSON + provider name.
- [ ] Implement `generate_image_assets(deck, provider, output_dir, force=False)`.
- [ ] Create `<output_dir>/assets/`.
- [ ] Save files as `assets/slide_01.png`, `assets/slide_02.png`, etc.
- [ ] Load existing `image_manifest.json` when present.
- [ ] Reuse asset when provider, prompt hash, and file path match.
- [ ] Record cache hits with `cached=True`.
- [ ] Record new generations with `cached=False`.
- [ ] Support `force=True` to regenerate.
- [ ] Write `art_spec.json`.
- [ ] Write `image_manifest.json`.
- [ ] Write manifest atomically enough for local CLI use.
- [ ] Prevent writes outside `output_dir`.
- [ ] Add unit tests for cache hit, cache miss, changed prompt, and force regeneration.

## 6. CLI

- [ ] Add `oka generate-images <deck_spec.json>`.
- [ ] Add `--output` option.
- [ ] Add `--provider` option.
- [ ] Add `--force` option.
- [ ] Validate input path exists and is a file.
- [ ] Read and validate DeckSpec.
- [ ] Use unique default output directory under `.runs/<YYYYMMDDTHHMMSSZ>-images/`.
- [ ] Load image provider.
- [ ] Generate or reuse assets.
- [ ] Print asset directory and manifest path.
- [ ] Ensure CLI does not open Keynote or call `keynote.*`.
- [ ] Add CLI tests.

## 7. Documentation

- [ ] Update README with `oka generate-images` example.
- [ ] Update CLAUDE.md and AGENTS.md with image asset generation workflow.
- [ ] Document fake provider and optional real provider configuration.
- [ ] Document cache behavior.
- [ ] Document that this change does not insert images into Keynote.

## 8. Quality Bar

- [ ] Run `uv run pytest`.
- [ ] Run `uv run ruff check .`.
- [ ] Confirm tests do not require network, real image API credentials, Keynote, or macOS Automation permissions.
