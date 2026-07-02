# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Open Keynote Agent** — an open-source macOS agent for creating and editing Apple Keynote presentations through natural-language, step-by-step workflows.

Project slug: `open-keynote-agent`. Python package: `open_keynote_agent`. CLI command: `oka`.

## Current State

The existing implementation is a **CLI file organizer** — the completed first learning milestone. It established the agent foundation:

- LLM provider abstraction (Bedrock, OpenAI, Gemini, Fake)
- Structured request validation (Pydantic)
- Deterministic local tools
- Confirmation before mutation
- Run logs
- Tests without cloud credentials

This milestone is not the long-term product focus. Future work is Keynote-specific.

## Future Direction

Next changes should build toward an interactive Keynote agent:

- Interactive agent runtime with session state, planner, executor, tool registry, and observations
- Keynote adapter using AppleScript or JXA first, Accessibility API fallback later
- Export to PDF and basic verification
- Session event stream suitable for a future Studio UI

## Setup

```bash
uv sync --all-extras                  # all providers + dev tools (recommended)
uv sync --extra dev              # core + pytest + ruff only
uv sync --extra dev --extra images    # add Pillow (needed for 013 overlay analysis)
uv sync --extra dev --extra bedrock   # add AWS Bedrock
uv sync --extra dev --extra openai    # add OpenAI
uv sync --extra dev --extra gemini    # add Gemini
```

When using a single provider extra, keep `--extra dev` included so pytest and ruff remain installed.

Copy `.env.example` to `.env` and set `OMA_LLM_PROVIDER` to `fake`, `bedrock`, `openai`, or `gemini`.

## Commands

```bash
uv run pytest                           # run all tests (no Keynote required)
uv run pytest tests/test_filesystem.py  # run a single test file
uv run pytest -k "test_move_files"      # run tests matching a name pattern
uv run ruff check .                     # lint
uv run oka --help                       # CLI help
uv run oka organize <folder> --dry-run
uv run oka organize <folder> --apply
uv run oka ask "organize ~/Downloads into PDFs and Images"
uv run oka session                      # interactive session with demo tools
uv run oka session --tools demo         # same as default
uv run oka session --tools keynote      # real Keynote via AppleScript (macOS only)
uv run oka generate-images <deck_spec_en.json> --dry-run --slides 1,4,9  # review prompts (no images)
uv run oka generate-images <deck_spec_en.json> --provider bedrock --slides 1,4,9  # generate images
uv run oka render-storybook <deck_spec.json> --images <image_manifest.json> --no-pdf  # render with images
RUN_KEYNOTE_INTEGRATION=1 uv run python -m pytest -m keynote_integration  # Keynote smoke test
```

All tests run without cloud credentials or API keys — the default `OMA_LLM_PROVIDER=fake` is used.

Unit tests do not require Keynote, `osascript`, macOS GUI access, or special permissions. The `keynote_integration` marker gates tests that call real Keynote; they are skipped unless `RUN_KEYNOTE_INTEGRATION=1` is set.

## Architecture (Readable Storybook Text Overlays — change 013)

### Overlay planner (`renderers/overlays.py`)
- `build_overlay_plan(slide, image_path)` → `OverlayPlan` — deterministic, no LLM; falls back to 012 fixed region if Pillow is unavailable or image cannot be read
- `OverlayRegion` — `name`, `x`, `y`, `width`, `height` (1280×720 canvas)
- `OverlayStyle` — `text_color` (`#FFFFFF` or `#2C1810`), `font_size`, `use_backing`, `backing_color`, `backing_opacity`, `shadow`
- `OverlayPlan` — `slide_index`, `region`, `style`, `text`, `diagnostics`
- Candidate regions: `bottom_band`, `top_band`, `left_panel`, `right_panel`, `center_caption`
- Luminance formula: `Y = 0.2126R + 0.7152G + 0.0722B` (BT.709); threshold `<128 → #FFFFFF`, `≥128 → #2C1810`
- Busyness: luminance stddev; `stddev > 45` or ambiguous luminance (`112–144`) → `use_backing=True`
- Scoring: `busyness + preference_penalty + center_penalty`; slide-kind preferences steer region choice
- Fallback (no Pillow / unreadable image): `bottom_band` at `x=90, y=500, w=1100, h=170`, `#FFFFFF`, `use_backing=False`
- Pillow is an optional dependency (`uv sync --extra images` or `--all-extras`)

### Image layout helpers (`renderers/templates.py`) — updated in 013
- `calls_for_slide_image_overlay(slide, image_path)` → `list[ProposedToolCall]` — calls `build_overlay_plan`, emits `keynote.add_text_box` with planned region and `font_color`; replaces `calls_for_slide_text_only` for image-backed slides

### Renderer integration (`renderers/storybook.py`) — updated in 013
- Image-backed slides now call `calls_for_slide_image_overlay(slide_spec, image_path)` instead of `calls_for_slide_text_only`
- Order: `keynote.add_image` full-bleed → `keynote.add_text_box` overlay (image rendered first, text on top)
- No-image fallback behavior unchanged

## Architecture (Image Assets to Storybook Renderer — change 012)

### Manifest loader (`images/loader.py`)
- `load_image_assets(manifest_path: Path)` → `dict[int, Path]` — loads `image_manifest.json`, resolves each asset path relative to the manifest directory, returns `slide_index → absolute Path`
- Rejects: manifest not found, invalid JSON/schema, absolute asset paths, duplicate `slide_index` entries, listed files that do not exist
- Missing slide indexes are allowed (fallback to emoji/shape visuals); extra manifest indexes are ignored by the renderer

### AppleScript builder (`applescript/scripts.py`) — updated in 012
- `add_image(slide, path, x, y, width, height)` → `str` — creates image on slide; sets position, width, and height via separate `set` statements; returns `count of images`; object IDs remain local-only

### Keynote tool (`tools/keynote.py`) — updated in 012
- `keynote.add_image` — validates path exists and is a file; converts to absolute path; validates geometry; registers image object with `type="image"`, `apple_class="image"`, plus `path/x/y/width/height/apple_index`

### Renderer integration (`renderers/storybook.py`) — updated in 012
- `render_storybook_deck(..., image_assets: dict[int, Path] | None = None)` — when an image exists for a slide, calls `keynote.add_image` full-bleed then `calls_for_slide_image_overlay` (013); when missing, uses `calls_for_slide` emoji/shape fallback
- Image-backed slides 2..N use semantic `blank` layout and skip the default Keynote title; slide 1 may keep the cover title
- `RenderResult` gains `image_count: int` and `missing_image_slides: list[int]`
- `image_assets=None` preserves 009 behavior exactly

### Image layout helpers (`renderers/templates.py`) — updated in 012
- `image_call_for_slide(slide, image_path)` → `ProposedToolCall` — deterministic full-bleed placement (`x=0`, `y=0`, `width=1280`, `height=720`)
- `calls_for_slide_text_only(slide)` → `list[ProposedToolCall]` — fixed overlay text template (no emoji, no shapes); superseded by `calls_for_slide_image_overlay` in 013

### CLI (`cli.py`) — updated in 012
- `oka render-storybook <deck_spec.json> --images <image_manifest.json>` — validates manifest before any Keynote mutation; prints image manifest path, images inserted count, and fallback slide list
- `--output` and `--no-pdf` preserved; no-image behavior unchanged

## Architecture (Image Prompt Director — change 011)

### Director module (`images/director.py`)
- `EMOJI_WORDS` dict — maps emoji to English object words
- `STYLE_MODES` dict — maps mode ID → preset description; `DEFAULT_STYLE_MODE = "soft_storybook_watercolor"`
- `DirectedImagePrompt` — Pydantic v2 model (`extra="forbid"`): `slide_index`, `slide_title`, `primary_scene`, `required_subjects`, `forbidden_subjects`, `composition`, `style_notes`, `story_context`, `prompt`, `negative_prompt`
- `build_directed_image_prompt(deck, slide, *, style_mode=DEFAULT_STYLE_MODE)` → `DirectedImagePrompt` — deterministic, no LLM; raises `ValueError` for unknown mode
- Prompt ordering for fixed preset modes: Image style anchor → Primary scene → Required subjects → Composition → Style → Story context → No-text instruction
- Prompt ordering for `deck_style`: Primary scene → Required subjects → Composition → Style → Story context → No-text instruction
- `primary_scene` leads with `slide.visual.description`; slide title appended as `[Slide: <title>]`
- `story_context` = `"{deck.title}[: {deck.subtitle}]"` — placed AFTER primary scene
- Required subjects: emoji words + noun phrases from description + slide title/subtitle/body (conservative heuristic)
- Generic forbidden subjects + slide-specific drift exclusions — no story-title branches
- Style guardrails in `negative_prompt`: `not photorealistic, not cinematic, not realistic portrait, not movie still, not 3D render, not adult editorial illustration`; in `deck_style`, any guardrail whose signal word appears positively in the mood string is suppressed (e.g. mood `"cinematic 3D render"` removes `not cinematic` and `not 3D render`); fixed preset modes always keep all guardrails
- **Fixed preset modes** (`soft_storybook_watercolor`, `cute_hand_drawn_cartoon`, `paper_cut_collage_storybook`): use preset as Style section; do NOT include `mood/typography/palette/decorations`; MAY include `audience`
- **`deck_style` mode**: uses `DeckSpec.style.mood/audience/typography/palette` and `visual.decorations`; no preset description
- Generated `art_spec.json` records the selected mode in `ImageSpec.style`, e.g. `"style": "soft_storybook_watercolor"`, instead of the legacy neutral `deck-specified` value

### Planner (`images/planner.py`) — updated in 011
- `build_slide_art_specs(deck, *, slide_indexes, style_mode=DEFAULT_STYLE_MODE)` — threads style_mode to director
- `ImageSpec.prompt` ← `directed.prompt`; `ImageSpec.negative_prompt` ← `directed.negative_prompt`

### Generator (`images/generator.py`) — updated in 011
- `generate_image_assets(..., dry_run=False, style_mode=DEFAULT_STYLE_MODE)` — threads both params through
- `dry_run=True`: builds `SlideArtSpec`s, writes `art_spec.json`, returns empty manifest, does NOT call provider, does NOT write `image_manifest.json`, does NOT create PNGs

### CLI dry-run (`cli.py`) — updated in 011
- `oka generate-images <deck_spec.json> --dry-run [--slides N] [--output PATH]`
- In dry-run: validates DeckSpec, parses `--slides`, writes `art_spec.json`, does NOT load real provider
- Default output dir suffix: `-dry-run` (vs `-images` for full generation)
- Recommended workflow: `--dry-run --slides 1,4,9` first to review prompts, then real generation

## Architecture (Image Asset Generation — change 010)

### Image package (`images/`)
- `images/schema.py` — `ImageSpec`, `SlideArtSpec`, `ImageAsset`, `ImageManifest` (Pydantic v2, `extra="forbid"`)
- `images/planner.py` — `build_slide_art_specs(deck)` → `list[SlideArtSpec]`; deterministic, no LLM
- `images/provider.py` — `ImageProvider` protocol; `FakeImageProvider` (stdlib-only 1×1 PNG); `BedrockImageProvider`, `OpenAIImageProvider`, `GeminiImageProvider`; `load_image_provider_from_env(provider_name)`
- `images/generator.py` — `generate_image_assets(deck, provider, *, output_dir, force=False)` → `ImageManifest`
- `SlideArtSpec.asset_filename` is a `@computed_field` derived from `slide_index` — e.g. `slide_03.png`
- Prompt hash: `sha256(f"{provider_name}\n{canonical_json}".encode("utf-8")).hexdigest()[:16]`, where `canonical_json` is `json.dumps(spec.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, separators=(",", ":"))`
- Cache: `cache_dir=None` (library default) disables shared cache; CLI passes `Path(".runs/image-cache/<provider>")` so repeated CLI runs share cache across timestamped dirs; also falls back to matching manifest entry in same `output_dir`
- `force=True` bypasses both shared cache and manifest fallback
- Manifest and art spec paths are relative to `output_dir`; `assets/` stores PNGs
- `art_spec.json` structure: `{"deck_title": ..., "slides": [SlideArtSpec, ...]}`
- Writes are atomic: `<file>.tmp` → `Path.replace()`
- The image package MUST NOT import `tools.keynote`, `applescript.*`, or `OsascriptRunner`
- `OKA_IMAGE_PROVIDER=fake|bedrock|openai|gemini` selects provider (default `fake`); `OKA_IMAGE_MODEL` selects real provider model where applicable
- Bedrock image region uses `OKA_IMAGE_AWS_REGION` first, then falls back to `AWS_REGION`; keep this separate from LLM region when needed
- OpenAI image generation uses `OPENAI_API_KEY`, optional `OPENAI_IMAGE_MODEL`, and optional `OKA_IMAGE_SIZE`
- Gemini image generation uses `GEMINI_API_KEY` and optional `GEMINI_IMAGE_MODEL`
- CLI: `oka generate-images <deck_spec_en.json|deck_spec.json> [--output PATH] [--provider TEXT] [--force]`; prefer `deck_spec_en.json` for real providers because it is the English image-generation source of truth
- Default output: `.runs/<YYYYMMDDTHHMMSSZ>-images/`

## Architecture (Storybook Renderer — change 009)

### Renderer package (`renderers/`)
- `renderers/templates.py` — `LAYOUT_FOR_KIND`, `FALLBACK_EMOJI`, `calls_for_slide(slide)` → `list[ProposedToolCall]`; all coordinates are constants on a 1280×720 canvas; chapter slides alternate visual left/right by index
- `renderers/storybook.py` — `render_storybook_deck(deck, registry, state, output_dir, export_pdf)` → `RenderResult`; `RenderResult` holds `tool_results: list[dict]` for `tool_results.jsonl`
- The renderer does NOT call any LLM and does NOT generate raw AppleScript
- Flow: `list_themes` → select theme → `create_document` → `list_layouts` → for each slide: (`add_slide` for slides 2..N only; `set_slide_title`; template object calls) → `export_pdf`
- Slide 1 is the Keynote default slide from `create_document`; never call `add_slide` for it
- `render_storybook_deck` raises `ValueError` if the first `SlideSpec.kind` is not `"cover"`
- Shapes: only `"rectangle"` is emitted; no `fill_color`, no `rounded_rectangle`/`oval`/`line`
- CLI: `oka render-storybook <deck_spec.json> [--output PATH] [--no-pdf]`
- Default output: `.runs/<YYYYMMDDTHHMMSSZ>-storybook/`

## Architecture (Deck Spec Planner — change 008)

### Deck package (`deck/`)
- `deck/schema.py` — `DeckSpec`, `DeckPlanBundle`, `SlideSpec`, `StyleSpec`, `VisualSpec` (Pydantic v2, `extra="forbid"`)
- `deck/planner.py` — `plan_deck_spec(...)` → `DeckSpec` for compatibility; `plan_deck_bundle(...)` → `{localized, english}` for CLI output
- `deck/outline.py` — `render_deck_outline(deck)` → `str`
- The `deck` package MUST NOT import `tools.keynote`, `applescript.*`, or `OsascriptRunner`
- `VisualSpec.decorations` are conceptual style notes; they are NOT `keynote.add_shape` enum values
- `DeckSpec.language` defaults to `None`; the planner instructs the LLM to infer it from the brief
- `deck_spec.json` is localized reader-visible content; `deck_spec_en.json` is the English image-generation and multilingual source of truth
- CLI: `oka deck-plan "<brief>" [--slides N] [--theme TEXT] [--output PATH]`
- Default output: `.runs/<YYYYMMDDTHHMMSSZ>/` (same convention as `runtime/session.py`); appends `-1`, `-2` suffix on collision
- On failure: exit non-zero, print a concise error, do not write partial files
- This change does NOT render Keynote slides — it produces the planning artifact only

## Architecture (Keynote Adapter — changes 005 + 006)

### Keynote tool set (`applescript/` + `tools/keynote.py`)
- `applescript/runner.py` — `ScriptRunner` protocol, `OsascriptRunner` (subprocess), `FakeScriptRunner` (tests)
- `applescript/scripts.py` — AppleScript string builders; `applescript_string()` escapes all user-controlled values; includes `list_themes()`, `list_layouts()`, and theme variant of `create_document()`
- `applescript/layout.py` — `_parse_newline_list()`, `LAYOUT_CANDIDATES`, `resolve_layout_name(semantic, available)`; do not put resolver logic in `scripts.py` or `tools/keynote.py`
- `tools/keynote.py` — `keynote.*` tool handlers + `register_keynote_tools(registry, runner)`; imports resolver from `applescript/layout.py`; no `_LAYOUT_MAP`
- CLI: `oka session --tools keynote` registers real tools; default `--tools demo` is unchanged
- When `--tools keynote` is selected, macOS may prompt for Automation permission to control Keynote

### Theme and layout discovery (change 006)
- `keynote.list_themes` / `keynote.list_layouts` — non-mutating tools that force newline output via `AppleScript's text item delimiters`; never split on commas
- `keynote.resolve_layout` — resolves semantic names (`title`, `title_body`, `blank`) to actual Keynote master slide names; fetches layouts from runner if not cached in context
- `keynote.create_document` — now accepts optional `theme` parameter; records `context["keynote"]["theme"]` only after script success
- `keynote.add_slide` — discovery-aware: reads `context["keynote"]["layouts"]` if present (no `list_layouts` call); fetches and caches layouts if absent
- `Parchment` is the recommended built-in storybook theme when available

### Object tools (change 007)
- `applescript/objects.py` — `validate_object_id`, `generate_object_id`, `commit_object_id`, `validate_geometry`, `hex_to_rgb_tuple`, `SHAPE_MAP`; keep all non-builder utilities here, not in `scripts.py`
- Object IDs follow `^[a-z][a-z0-9_]{0,63}$`; generated as `slide_{slide:02d}_{kind}_{n}` where kind is `text_box`, `emoji`, or `shape`
- `object_id` is local session metadata only; Keynote text/shape objects are tracked by stored `apple_class` + `apple_index`
- `scripts.add_text_box` / `scripts.add_shape` return created-object collection indexes; `scripts.move_object` / `scripts.resize_object` use the stored AppleScript class/index reference
- `keynote.add_emoji_text` calls `scripts.add_text_box(text=emoji, ...)` — no separate builder
- Context schema: `context["keynote"]["objects"][object_id]` stores `{object_id, slide, type, apple_class, apple_index, x, y, width, height, ...}`; `context["keynote"]["slides"]["N"]["objects"]` is the per-slide index using **string** keys
- Context updates are success-only: registry is never mutated when the runner returns a failure

## Architecture (File Organizer Milestone)

The data flow is: **CLI → organizer (plan) → filesystem (execute) → session (log)**

### Core data models (`organizer.py`)
- `OrganizePlan` — the central value passed between layers, contains `operations: list[MoveOperation]` and `skipped: list[SkippedFile]`
- `build_organize_plan(target_dir, categories=None)` — pure function, no I/O side effects, safe to call repeatedly

### Execution boundary (`filesystem.py`)
- `move_files(plan)` — the **only** function that mutates the filesystem; re-validates paths inside `target_dir` and skips rather than overwriting

### LLM layer (`llm/`)
- `LLMClient` is a `Protocol` with a single method `complete_json(messages, schema) -> dict`
- `parser.py::load_llm_client_from_env()` selects the provider via `OMA_LLM_PROVIDER`
- `parser.py::parse_natural_language_request()` calls the LLM and validates output through `LLMPlanResponse` (Pydantic) — the result feeds `target_dir` and `categories` into `build_organize_plan`
- `FakeLLMClient` is used in all tests; inject `FakeLLMClient(response={...})` to control LLM output

### Runtime logging (`runtime/session.py`)
- Every CLI run writes to `.runs/<YYYYMMDDTHHMMSSZ>/`: `request.json`, `plan.json`, `tool_calls.jsonl`, `result.json`

### CLI (`cli.py`)
- Two main commands: `organize` (rule-based, no LLM) and `ask` (LLM-driven)
- Both default to dry-run unless `--apply` is passed; `handle_plan()` owns the confirmation prompt
