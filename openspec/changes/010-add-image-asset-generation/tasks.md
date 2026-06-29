# Tasks

## 1. Image Package

- [x] Add `src/open_keynote_agent/images/__init__.py`.
- [x] Add `src/open_keynote_agent/images/schema.py`.
- [x] Add `src/open_keynote_agent/images/planner.py`.
- [x] Add `src/open_keynote_agent/images/provider.py`.
- [x] Add `src/open_keynote_agent/images/generator.py`.
- [x] Ensure image package does not import Keynote tools or AppleScript modules.

## 2. Models

- [x] Define `ImageSpec`.
- [x] Define `SlideArtSpec`.
- [x] Define `ImageAsset`.
- [x] Define `ImageManifest`.
- [x] Define `ImageGenerationResult`.
- [x] Use Pydantic v2 with `extra="forbid"`.
- [x] Validate non-empty image prompt.
- [x] Validate `aspect_ratio="16:9"`.
- [x] Validate `output_format="png"`.
- [x] Validate `slide_index >= 1`.
- [x] Implement `SlideArtSpec.asset_filename` as a `@computed_field` derived from `slide_index`.
- [x] Store manifest `assets_dir` as relative path `"assets"`.
- [x] Store `ImageAsset.path` relative to `output_dir`, e.g. `assets/slide_01.png`.
- [x] Add unit tests for valid and invalid models.

## 3. Art Spec Planner

- [x] Implement `build_slide_art_specs(deck)`.
- [x] Produce one `SlideArtSpec` per DeckSpec slide.
- [x] Include deck title in prompts.
- [x] Include style mood and audience in prompts.
- [x] Include slide title, subtitle, and body in prompts.
- [x] Include visual description, emoji, and decorations in prompts.
- [x] Include "no text, no captions, no letters, no watermark" instruction.
- [x] Keep prompt construction deterministic.
- [x] Add unit tests for prompt contents and deterministic output.

## 4. Image Provider

- [x] Define `ImageProvider` protocol with `name: str` class attribute and `generate(...) -> ImageGenerationResult`.
- [x] Make providers raise clear exceptions on failure.
- [x] Implement `FakeImageProvider` (stdlib-only 1×1 white PNG via struct + zlib).
- [x] Implement `BedrockImageProvider` as the primary explicit real image provider.
- [x] `BedrockImageProvider` reads model id from `OKA_IMAGE_MODEL`.
- [x] `BedrockImageProvider` uses `AWS_REGION` and `AWS_PROFILE` conventions from existing LLM adapter.
- [x] `BedrockImageProvider` fails clearly when `OKA_IMAGE_MODEL` is missing.
- [x] Add provider loader `load_image_provider_from_env(provider_name)` using `OKA_IMAGE_PROVIDER` with default `fake`.
- [x] Loader supports `fake` and `bedrock`; raises `UnsupportedImageProviderError` for unknown names.
- [x] Treat `openai` as a reserved future provider until `OpenAIImageProvider` is implemented.
- [x] `BedrockImageProvider` lazy-imports boto3; raises `ImportError` with clear message if absent.
- [x] Add clear error for unknown or unconfigured providers.
- [x] Ensure tests never call real provider.

## 5. Generation And Cache

- [x] Implement prompt hash: `sha256(f"{provider_name}\n{canonical_json}").hexdigest()[:16]`.
- [x] Implement `generate_image_assets(deck, provider, *, output_dir, force=False, cache_dir=None)`.
- [x] Create `<output_dir>/assets/`.
- [x] Save files as `assets/slide_01.png`, `assets/slide_02.png`, etc.
- [x] Load existing `image_manifest.json` from `output_dir` when present.
- [x] When `cache_dir` is supplied: check `<cache_dir>/<hash>.png` before generating; populate after generating.
- [x] Fall back to same-`output_dir` manifest entry when provider, prompt hash, and file path all match.
- [x] Record cache hits with `cached=True`, new generations with `cached=False`.
- [x] Support `force=True` to bypass cache and regenerate.
- [x] Write `art_spec.json` as `{"deck_title": ..., "slides": [...]}`.
- [x] Write `image_manifest.json`.
- [x] Write both files atomically via `<file>.tmp` → `Path.replace()`.
- [x] `cache_dir=None` (library default) disables shared cache — prevents test pollution.
- [x] `cache_dir` is optional; when supplied, it enables shared cache, and when `None`, shared cache is disabled.
- [x] Add unit tests for cache hit (shared cache), cache miss, changed prompt, and force regeneration.

## 6. CLI

- [x] Add `oka generate-images <deck_spec.json>`.
- [x] Add `--output` option.
- [x] Add `--provider` option.
- [x] Add `--force` option.
- [x] Validate input path exists and is a file.
- [x] Read and validate DeckSpec.
- [x] Use unique default output directory under `.runs/<YYYYMMDDTHHMMSSZ>-images/`.
- [x] Load image provider via `load_image_provider_from_env`.
- [x] Generate or reuse assets via `generate_image_assets`; callers may pass `cache_dir` to enable shared cache.
- [x] Print asset directory and manifest path.
- [x] Clean up auto-created default dir on failure.
- [x] Ensure CLI does not open Keynote or call `keynote.*`.
- [x] Add CLI tests.
- [x] Add CLI test proving `--force` regenerates (cached=False in manifest).

## 7. Documentation

- [x] Update README with `oka generate-images` example.
- [x] Update CLAUDE.md and AGENTS.md with image asset generation workflow.
- [x] Document fake provider and Bedrock provider configuration.
- [x] Document cache behaviour and `--force`.
- [x] Document that this change does not insert images into Keynote.

## 8. Quality Bar

- [x] Run `uv run pytest` — 450 passed, 2 skipped.
- [x] Run `uv run ruff check .` — clean.
- [x] Confirm tests do not require network, real image API credentials, Keynote, or macOS Automation permissions.
