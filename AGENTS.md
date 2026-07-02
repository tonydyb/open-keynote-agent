# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

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
uv sync --extra dev              # core + pytest + ruff + Pillow (Pillow is now in dev)
uv sync --extra dev --extra images    # same as above (images extra also brings Pillow)
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
RUN_KEYNOTE_INTEGRATION=1 uv run python -m pytest -m keynote_integration  # Keynote smoke test
```

All tests run without cloud credentials or API keys — the default `OMA_LLM_PROVIDER=fake` is used.

Unit tests do not require Keynote, `osascript`, macOS GUI access, or special permissions. The `keynote_integration` marker gates tests that call real Keynote; they are skipped unless `RUN_KEYNOTE_INTEGRATION=1` is set.

When running `oka session --tools keynote`, macOS may prompt for permission to control Keynote via Automation. Grant it when asked.

## Architecture (Readable Storybook Text Overlays — change 013)

### Overlay planner (`renderers/overlays.py`)
- `build_overlay_plan(slide, image_path)` → `OverlayPlan` — deterministic, no LLM; falls back to fixed 012 region on Pillow error or unreadable image
- Candidate regions (1280×720): `bottom_band`, `top_band`, `left_panel`, `right_panel`, `center_caption`
- Luminance: BT.709 `Y = 0.2126R + 0.7152G + 0.0722B`; `<128 → #FFFFFF`, `≥128 → #2C1810`
- Busyness: luminance stddev; `>45` or ambiguous luminance → `use_backing=True`
- Slide-kind preferences steer region scoring; lower score wins
- `OverlayPlan.diagnostics` records `mean_luminance`, `stddev_luminance`, `selected_region`, `text_color`, `use_backing`, `fallback`

### Templates (`renderers/templates.py`) — updated in 013
- `calls_for_slide_image_overlay(slide, image_path)` → `list[ProposedToolCall]` — calls `build_overlay_plan`; emits `keynote.add_text_box` with planned region and `font_color`; supersedes `calls_for_slide_text_only` for image-backed slides

### Renderer (`renderers/storybook.py`) — updated in 013
- Image-backed slides now call `calls_for_slide_image_overlay` (image-aware color + region) instead of `calls_for_slide_text_only`
- Insertion order: `keynote.add_image` full-bleed → `keynote.add_text_box` overlay (image first, text on top)

## Architecture (Image Assets to Storybook Renderer — change 012)

### Manifest loader (`images/loader.py`)
- `load_image_assets(manifest_path)` → `dict[int, Path]` — resolves asset paths relative to manifest directory; fails early if manifest invalid, asset paths are absolute, indexes duplicated, or listed files missing

### Keynote tool (`tools/keynote.py`) — updated in 012
- `keynote.add_image(slide, path, x, y, width, height, object_id?)` — inserts PNG into slide; stores `type="image"` entry in object registry; validates file existence before AppleScript

### Renderer (`renderers/storybook.py`) — updated in 012
- `render_storybook_deck(..., image_assets=None)` — optional `dict[int, Path]`; slides with images use `keynote.add_image` + `calls_for_slide_image_overlay` (013); slides without use 009 emoji/shape fallback
- Image-backed slides 2..N use semantic `blank` layout and skip the default Keynote title; slide 1 may keep the cover title
- `RenderResult` gains `image_count` and `missing_image_slides`
- `image_assets=None` preserves 009 behavior unchanged

### Templates (`renderers/templates.py`) — updated in 012
- `image_call_for_slide(slide, path)` — deterministic full-bleed `keynote.add_image` call (`x=0`, `y=0`, `width=1280`, `height=720`)
- `calls_for_slide_text_only(slide)` — deterministic overlay text template (no emoji, no shapes) used when image provides primary visual

### CLI — updated in 012
- `oka render-storybook <deck_spec.json> --images <image_manifest.json>` — validates manifest before Keynote; fallback visuals for missing images; invalid manifest exits before Keynote mutation
- Does NOT generate images; consumes `image_manifest.json` produced by 010/011

## Architecture (Image Prompt Director — change 011)

### Director module (`images/director.py`)
- `EMOJI_WORDS` dict — maps emoji to English object words
- `DirectedImagePrompt` — Pydantic v2 model (`extra="forbid"`): `slide_index`, `slide_title`, `primary_scene`, `required_subjects`, `forbidden_subjects`, `composition`, `style_notes`, `story_context`, `prompt`, `negative_prompt`
- `STYLE_MODES` dict — maps mode ID → preset description; `DEFAULT_STYLE_MODE = "soft_storybook_watercolor"`
- `build_directed_image_prompt(deck, slide, *, style_mode=DEFAULT_STYLE_MODE)` → `DirectedImagePrompt` — deterministic, no LLM; raises `ValueError` for unknown mode
- Prompt order for fixed preset modes: Image style anchor → Primary scene → Required subjects → Composition → Style → Story context → No-text instruction
- Prompt order for `deck_style`: Primary scene → Required subjects → Composition → Style → Story context → No-text instruction
- `primary_scene` leads with `slide.visual.description`; slide title appended as `[Slide: <title>]` (avoids broad story priors)
- `story_context` = `"{deck.title}[: {deck.subtitle}]"` — placed after primary scene
- Required subjects extracted from: emoji words, noun phrases from `visual.description`, slide title/subtitle/body
- Generic forbidden subjects + `DeckSpec.style.avoid`; conservative slide-specific drift exclusions — no story-title branches
- Fixed preset modes (`soft_storybook_watercolor`, `cute_hand_drawn_cartoon`, `paper_cut_collage_storybook`): use preset as Style; do NOT include `mood/typography/palette/decorations`; MAY include `audience`
- `deck_style` mode: uses `DeckSpec.style.mood/audience/typography/palette` and `visual.decorations`; no preset description
- `ImageSpec.style` in generated `art_spec.json` stores the selected style mode ID, not the legacy neutral `deck-specified` value
- Style guardrails always in `negative_prompt` (`not photorealistic`, `not cinematic`, etc.); suppressed per-guardrail in `deck_style` when the mood string positively requests that visual style
- CLI: `oka generate-images <deck_spec_en.json> --dry-run [--slides N] [--style MODE]` — writes `art_spec.json`, no provider call, no PNGs

## Architecture (Image Asset Generation — change 010)

### Image package (`images/`)
- `images/schema.py` — `ImageSpec`, `SlideArtSpec`, `ImageAsset`, `ImageManifest` (Pydantic v2, `extra="forbid"`)
- `images/planner.py` — `build_slide_art_specs(deck)` → `list[SlideArtSpec]`; delegates to `build_directed_image_prompt`
- `images/director.py` — `build_directed_image_prompt(deck, slide, *, style_mode)` → `DirectedImagePrompt`; prompt compiler with fixed-preset style anchors and scene-before-story ordering
- `images/provider.py` — `ImageProvider` protocol; `FakeImageProvider` (stdlib-only PNG); `BedrockImageProvider`, `OpenAIImageProvider`, `GeminiImageProvider`; `load_image_provider_from_env(name)`
- `images/generator.py` — `generate_image_assets(deck, provider, *, output_dir, force=False, dry_run=False, style_mode=DEFAULT_STYLE_MODE)` → `ImageManifest`
- `SlideArtSpec.asset_filename` is a `@computed_field` — e.g. `slide_03.png`
- Prompt hash: `sha256(f"{provider_name}\n{canonical_json}".encode("utf-8")).hexdigest()[:16]`, where `canonical_json` is `json.dumps(spec.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, separators=(",", ":"))`
- Cache: `cache_dir=None` disables shared cache (library/test default); CLI passes `.runs/image-cache/<provider>` so runs share cache across timestamped dirs; also falls back to matching manifest entry in same `output_dir`; `force=True` bypasses both
- `dry_run=True`: writes `art_spec.json` only; no provider call, no PNGs, no `image_manifest.json`
- Asset paths in manifest are relative to `output_dir`; atomic writes via `<file>.tmp` → `Path.replace()`
- The image package MUST NOT import Keynote tools, AppleScript builders, or `OsascriptRunner`
- `OKA_IMAGE_PROVIDER=fake|bedrock|openai|gemini`; `OKA_IMAGE_MODEL` selects real provider model where applicable
- Bedrock image region uses `OKA_IMAGE_AWS_REGION` first, then falls back to `AWS_REGION`; keep this separate from LLM region when needed
- OpenAI image generation uses `OPENAI_API_KEY`, optional `OPENAI_IMAGE_MODEL`, and optional `OKA_IMAGE_SIZE`
- Gemini image generation uses `GEMINI_API_KEY` and optional `GEMINI_IMAGE_MODEL`
- CLI: `oka generate-images <deck_spec_en.json|deck_spec.json> [--output PATH] [--provider TEXT] [--slides TEXT] [--force] [--dry-run] [--style MODE]`; prefer `deck_spec_en.json` for real providers

## Architecture (Storybook Renderer — change 009)

### Renderer package (`renderers/`)
- `renderers/templates.py` — `LAYOUT_FOR_KIND`, `FALLBACK_EMOJI`, `calls_for_slide(slide)` → `list[ProposedToolCall]`; 1280×720 canvas constants; chapter alternates left/right by slide index
- `renderers/storybook.py` — `render_storybook_deck(deck, registry, state, output_dir, export_pdf)` → `RenderResult`
- `RenderResult.tool_results: list[dict]` — serialized records from every `execute_plan` call; written to `tool_results.jsonl` by the CLI
- Flow: `list_themes` → select theme (deck.theme > Parchment > Basic White > first) → `create_document` → `list_layouts` → slides (skip `add_slide` for slide 1; call it for slides 2..N) → optional `export_pdf`
- First `SlideSpec.kind` must be `"cover"` or `ValueError` is raised before any Keynote mutation
- No LLM calls; no raw AppleScript; shapes limited to `"rectangle"` without `fill_color`
- CLI: `oka render-storybook <deck_spec.json> [--output PATH] [--no-pdf]`

## Architecture (Deck Spec Planner — change 008)

### Deck package (`deck/`)
- `deck/schema.py` — `DeckSpec`, `DeckPlanBundle`, `SlideSpec`, `StyleSpec`, `VisualSpec` (Pydantic v2, `extra="forbid"`)
- `deck/planner.py` — `plan_deck_spec(...)` → `DeckSpec` for compatibility; `plan_deck_bundle(...)` → `{localized, english}` for CLI output
- `deck/outline.py` — `render_deck_outline(deck)` → `str`
- The `deck` package MUST NOT import `tools.keynote`, `applescript.*`, or `OsascriptRunner`
- `VisualSpec.decorations` are conceptual style notes; they are NOT `keynote.add_shape` enum values
- `DeckSpec.language` defaults to `None`; inferred from the brief's primary language by the LLM
- `deck_spec.json` is localized reader-visible content; `deck_spec_en.json` is the English image-generation and multilingual source of truth
- CLI: `oka deck-plan "<brief>" [--slides N] [--theme TEXT] [--output PATH]`
- Default output directory: `.runs/<YYYYMMDDTHHMMSSZ>/`; appends `-1`, `-2` on timestamp collision
- On failure: exit non-zero, print concise error, do not write partial files
- This change does NOT render Keynote slides — the planning artifact only

## Architecture (Keynote Adapter — changes 005 + 006)

### Keynote tool set (`applescript/` + `tools/keynote.py`)
- `applescript/runner.py` — `ScriptRunner` protocol, `OsascriptRunner` (subprocess), `FakeScriptRunner` (tests)
- `applescript/scripts.py` — AppleScript string builders; `applescript_string()` escapes all user-controlled values; includes `list_themes()`, `list_layouts()`, and theme variant of `create_document()`
- `applescript/layout.py` — `_parse_newline_list()`, `LAYOUT_CANDIDATES`, `resolve_layout_name(semantic, available)`
- `tools/keynote.py` — `keynote.*` tool handlers + `register_keynote_tools(registry, runner)`; imports resolver from `applescript/layout.py`; no `_LAYOUT_MAP`

### Theme and layout discovery (change 006)
- `keynote.list_themes` / `keynote.list_layouts` — use `AppleScript's text item delimiters` for newline output; never split on commas
- `keynote.resolve_layout` — resolves `title`, `title_body`, `blank` to actual Keynote master slide names
- `keynote.add_slide` — reads cached `context["keynote"]["layouts"]`; fetches via runner if absent
- `Parchment` is the recommended built-in storybook theme

### Object tools (change 007)
- `applescript/objects.py` — `validate_object_id`, `generate_object_id`, `commit_object_id`, `validate_geometry`, `hex_to_rgb_tuple`, `SHAPE_MAP`
- Object IDs: `^[a-z][a-z0-9_]{0,63}$`; auto-generated as `slide_{slide:02d}_{kind}_{n}`
- `object_id` is local session metadata only; Keynote text/shape objects are tracked by stored `apple_class` + `apple_index`
- `scripts.add_text_box` / `scripts.add_shape` return created-object collection indexes; `scripts.move_object` / `scripts.resize_object` use the stored AppleScript class/index reference
- `keynote.add_emoji_text` calls `scripts.add_text_box` internally (no separate AppleScript builder)
- Context: `context["keynote"]["objects"][oid]` stores geometry plus `apple_class`/`apple_index`; `context["keynote"]["slides"]["N"]["objects"]` uses string slide keys
- Object context is a best-effort local mirror; manual Keynote edits outside the agent will not be reflected

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
