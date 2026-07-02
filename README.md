# Open Keynote Agent

An open-source macOS agent for creating and editing Apple Keynote presentations through natural-language, step-by-step workflows.

Project slug: `open-keynote-agent`.

Python package: `open_keynote_agent`. CLI command: `oka`.

## Current Milestone

The current implementation is a CLI file organizer. It is the first learning milestone for the agent foundation:

- LLM provider abstraction
- structured request validation
- deterministic local tools
- confirmation before mutation
- run logs
- tests without cloud credentials

Future work is focused on Keynote-specific agent workflows.

## Quickstart

1. Sync dependencies and install the package:

```bash
uv sync
```

2. View the CLI help:

```bash
uv run oka --help
```

3. Run the version command:

```bash
uv run oka version
```

4. Preview deterministic file organization:

```bash
uv run oka organize ./demo --dry-run
```

5. Preview natural-language file organization:

```bash
uv run oka ask "Organize ./demo into PDFs and Images"
```

This command requires `OMA_LLM_PROVIDER` to be set to `bedrock`, `openai`, or `gemini`. The `fake` provider is only for tests.

6. Apply a natural-language plan after confirmation:

```bash
uv run oka ask "Organize ./demo into PDFs and Images" --apply
```

## Environment

Copy `.env.example` to `.env` and configure your preferred LLM provider when ready.

For example, using OpenAI:

```bash
OMA_LLM_PROVIDER=openai
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=gpt-4o
```

## LLM Provider Setup

Set `OMA_LLM_PROVIDER` to one of:

- `fake` for local testing
- `bedrock` for AWS Bedrock
- `openai` for OpenAI API
- `gemini` for Gemini API

Configure provider environment variables:

- Bedrock: `AWS_PROFILE`, `AWS_REGION`, `BEDROCK_MODEL_ID`
- Bedrock image generation: `OKA_IMAGE_AWS_REGION`, `OKA_IMAGE_MODEL`
- OpenAI: `OPENAI_API_KEY`, optional `OPENAI_MODEL`
- Gemini: `GEMINI_API_KEY`, optional `GEMINI_MODEL`

The CLI uses `load_llm_client_from_env()` to select the provider without leaking provider logic into the organizer.

Natural-language requests default to dry-run. File moves only happen when apply mode is requested and the confirmation prompt is accepted.

## Safety Notes

- `oka organize` and `oka ask` default to previewing the move plan without changing files.
- `--apply` still requires an explicit confirmation prompt before any file is moved.
- Existing destination files are never overwritten; conflicting moves are skipped and recorded.
- File operations are limited to regular files inside the target directory.
- Tests use `FakeLLMClient` and do not require cloud credentials, API keys, or network access.
- Each run writes audit artifacts under `.runs/<run-id>/`.

## Keynote Adapter

`oka session` supports two tool sets:

```bash
oka session                   # default: demo.* tools (no Keynote required)
oka session --tools demo      # same as default
oka session --tools keynote   # real Keynote automation via AppleScript
```

When `--tools keynote` is selected, macOS may prompt for permission to control Keynote via Automation. Grant the permission when asked.

### Theme and layout discovery (change 006)

Discover installed themes and document layouts at runtime so the agent works
across Keynote versions and user machines without hard-coded layout names:

```text
oka> Use tool keynote.list_themes
oka> Use tool keynote.create_document with name three-pigs and theme Parchment
oka> Use tool keynote.list_layouts
oka> Use tool keynote.resolve_layout with layout title_body
oka> Use tool keynote.add_slide with layout title_body
```

`Parchment` is the recommended built-in storybook theme when available. The
semantic layout names (`title`, `title_body`, `blank`) are stable across themes;
the adapter resolves them to the actual Keynote master slide name at runtime.

### Keynote tools

| Tool | Mutating | Description |
|---|---|---|
| `keynote.list_themes` | no | Return installed Keynote theme names. |
| `keynote.create_document` | yes | Create a new document, optionally with a named theme. |
| `keynote.list_layouts` | no | Return slide layout names for the front document. |
| `keynote.resolve_layout` | no | Resolve a semantic layout name to a real Keynote name. |
| `keynote.add_slide` | yes | Add a slide via semantic layout resolution. |
| `keynote.set_slide_title` | yes | Set the title of a slide (1-indexed). |
| `keynote.set_slide_body` | yes | Set the body text of a slide (1-indexed). |
| `keynote.export_pdf` | yes | Export the front document to PDF. |
| `keynote.get_document_info` | no | Return document name and slide count. |
| `keynote.add_text_box` | yes | Add a text box with optional font size and color. |
| `keynote.add_emoji_text` | yes | Add a large emoji as a text object. |
| `keynote.add_shape` | yes | Add an MVP default rectangle shape. |
| `keynote.move_object` | yes | Move a tracked object to a new position. |
| `keynote.resize_object` | yes | Resize a tracked object. |

### Integration tests

Skipped by default. Require macOS, Keynote installed, and Automation permission:

```bash
RUN_KEYNOTE_INTEGRATION=1 uv run python -m pytest -m keynote_integration -s
```

Normal tests do not require Keynote, `osascript`, macOS GUI access, or any special permissions.

## Deck Planning

`oka deck-plan` converts a natural-language presentation brief into a validated
`DeckSpec` JSON and a readable slide outline, **without opening Keynote**:

```bash
oka deck-plan "请为我制作一个关于《三只小猪》故事的精美 Keynote 演示文稿" \
    --slides 8 --theme Parchment
```

Options:

| Option | Default | Description |
|---|---|---|
| `--slides` | (from brief) | Slide count hint (1..20) |
| `--theme` | Parchment | Keynote theme hint |
| `--output` | `.runs/<timestamp>/` | Output directory |

The command writes bilingual planning artifacts to the output directory:

- `request.json` — the original brief and options
- `deck_spec.json` — localized reader-visible `DeckSpec` (UTF-8, `ensure_ascii=False`)
- `deck_spec_en.json` — English image-generation and multilingual source-of-truth `DeckSpec`
- `outline.md` — localized human-readable slide outline for review
- `outline_en.md` — English slide outline

The outline is printed to the terminal so you can inspect the plan before rendering.

This command does **not** open Keynote and does **not** call any `keynote.*` tools.
The next change (`009`) will use the `DeckSpec` to render slides using deterministic
layout templates.

## Storybook Renderer

`oka render-storybook` converts a `deck_spec.json` produced by `oka deck-plan` into a real
Keynote presentation, and optionally exports a PDF:

```bash
# Step 1: plan
oka deck-plan "请为我制作一个关于《三只小猪》的8页童话绘本风Keynote" --slides 8 --output /tmp/pigs-plan

# Step 2: render (opens Keynote)
oka render-storybook /tmp/pigs-plan/deck_spec.json --output /tmp/pigs-rendered
```

Options:

| Option | Default | Description |
|---|---|---|
| `--output` | `.runs/<timestamp>-storybook/` | Output directory |
| `--no-pdf` | off | Skip PDF export |

Options:

| Option | Default | Description |
|---|---|---|
| `--images` | (none) | Path to `image_manifest.json` from `oka generate-images` |
| `--no-pdf` | off | Skip PDF export |

The command requires macOS Automation permission to control Keynote.

**Limitations (change 009/012 MVP):**
- Shapes limited to `rectangle` only — no `rounded_rectangle`, `oval`, or `line`.
- No shape fill color (`fill_color` is deferred until a verified Keynote AppleScript path exists).
- No custom fonts or animation.
- No LLM is called — the renderer is fully deterministic.

### Rendering with generated images (change 012)

After generating images with `oka generate-images`, pass the manifest to `oka render-storybook`:

```bash
# Step 1: plan
oka deck-plan "请为我制作一个关于《三只小猪》的8页绘本风Keynote" --slides 8 --output /tmp/pigs-plan

# Step 2: generate illustrations
oka generate-images /tmp/pigs-plan/deck_spec_en.json \
  --provider bedrock --style soft_storybook_watercolor \
  --output /tmp/pigs-art

# Step 3: render with images (opens Keynote)
oka render-storybook /tmp/pigs-plan/deck_spec.json \
  --images /tmp/pigs-art/image_manifest.json \
  --output /tmp/pigs-keynote
```

The renderer inserts each available image as a full-bleed 1280x720 illustration. For image-backed slides after the cover, it uses a blank layout, skips the default presentation title, and renders body text as an overlay above the image using **image-aware text color and placement** (change 013):

- Pillow analyses each candidate region (bottom, top, left, right, center) for mean luminance and busyness.
- Dark backgrounds get white text (`#FFFFFF`); bright backgrounds get dark-brown text (`#2C1810`).
- Busy or ambiguous regions set `use_backing=True` in diagnostics (backing panel rendering is deferred to a future spec).
- The lowest-scoring region is selected based on busyness and slide-kind preferences.
- If Pillow is unavailable or the image cannot be read, the renderer falls back to the fixed 012 bottom-band overlay.

Slides not covered by the manifest use the existing emoji/shape fallback visual. Images listed in the manifest but whose files are missing fail before Keynote is opened.

`render_result.json` includes `image_count` and `missing_image_slides`. `tool_results.jsonl` includes `keynote.add_image` entries.

## Image Asset Generation

`oka generate-images` converts a `DeckSpec` into per-slide illustration PNG files
without opening Keynote.

### Recommended workflow: review prompts first

Use `--dry-run` to write `art_spec.json` with the directed image prompts and inspect them
before spending image-generation credits:

```bash
# Step 1: plan
oka deck-plan "Create an 8-slide Three Little Pigs storybook" --slides 8 --output /tmp/pigs-plan

# Step 2: review prompts for selected slides (no API call, no PNG)
oka generate-images /tmp/pigs-plan/deck_spec_en.json \
  --dry-run --slides 1,4,8 \
  --output /tmp/pigs-prompts

# Step 3: generate images for reviewed slides
OKA_IMAGE_AWS_REGION=us-west-2 \
OKA_IMAGE_MODEL=stability.stable-image-core-v1:1 \
  oka generate-images /tmp/pigs-plan/deck_spec_en.json \
  --provider bedrock --slides 1,4,8 \
  --output /tmp/pigs-art

# Or generate all slides with the fake provider (no API key needed)
oka generate-images /tmp/pigs-plan/deck_spec_en.json --output /tmp/pigs-art
```

Use `deck_spec_en.json` for real image generation when it is available. `deck_spec.json`
is still accepted, but localized non-English scene text may produce weaker image results.

Options:

| Option | Default | Description |
|---|---|---|
| `--output` | `.runs/<timestamp>-images/` | Output directory |
| `--provider` | from `OKA_IMAGE_PROVIDER` or `fake` | Image provider |
| `--slides` | all slides | Comma/range selector, e.g. `1,4,9-12` |
| `--dry-run` | off | Write `art_spec.json` only; no provider call, no PNGs |
| `--force` | off | Ignore cache and regenerate all images |

`--dry-run` output:

```text
<output>/
  art_spec.json           — one SlideArtSpec per slide (directed prompts)
```

Full generation output:

```text
<output>/
  art_spec.json           — one SlideArtSpec per slide (prompts)
  image_manifest.json     — provider, hashes, paths, cache status
  assets/
    slide_01.png
    slide_02.png
    ...
```

### Prompt director (change 011)

Each slide's prompt is compiled by `build_directed_image_prompt` in `images/director.py`.
The prompt format keeps the current slide scene before story context to avoid broad story-title priors. Fixed preset modes also put a short style anchor first so image models follow the selected visual style:

```text
Image style, follow strongly:
<selected fixed style mode and preset description>

Primary scene, follow exactly:
<slide.visual.description> [Slide: <slide.title>]

Required subjects:
- <noun phrase from description>
- <emoji-derived object word>

Composition:
<kind-based default>

Style:
<style mode preset or DeckSpec.style fields>

Story context:
<deck.title>. Use the story only as background context; do not add unrelated story elements.

No text, no captions, no letters, no watermark.
```

The director is deterministic and calls no LLM. The `--style` option selects a visual mode:

| Style mode | Description |
|---|---|
| `soft_storybook_watercolor` | Gentle watercolor children's picture-book look (default) |
| `cute_hand_drawn_cartoon` | Cute hand-drawn cartoon with expressive characters |
| `paper_cut_collage_storybook` | Paper-cut collage with layered textures |
| `deck_style` | Uses `DeckSpec.style.mood / palette / typography` directly |

Fixed preset modes (`soft_storybook_watercolor`, `cute_hand_drawn_cartoon`, `paper_cut_collage_storybook`) inject the preset description as the Style section and do **not** automatically mix in `DeckSpec.style.mood`, palette, or typography. `deck_style` uses DeckSpec fields exclusively and applies no preset.

For fixed preset modes, the preset also appears at the start of the provider prompt as `Image style, follow strongly:`. `deck_style` stays scene-first.

`art_spec.json` also records the selected mode in `image.style`, for example `"style": "soft_storybook_watercolor"`.

Style guardrails (`not photorealistic`, `not cinematic`, `not 3D render`, etc.) are always added to `negative_prompt`. In `deck_style`, guardrails whose keyword appears in the mood string are suppressed — e.g. a mood of `"cinematic 3D fairy-tale render"` removes `not cinematic` and `not 3D render`.

**Recommended workflow:**

```bash
# Preview prompts for a few slides
uv run oka generate-images deck_spec_en.json --dry-run --slides 1,4,9

# Try different styles
uv run oka generate-images deck_spec_en.json --dry-run --slides 1,4,9 --style cute_hand_drawn_cartoon

# Generate with chosen style
uv run oka generate-images deck_spec_en.json --provider bedrock --style soft_storybook_watercolor
```

**Caching:** on a second run with `--output <existing-dir>`, unchanged prompts reuse the
existing PNG files. Changed prompts or `--force` trigger regeneration.

**Providers:**

| Provider | Requires | Description |
|---|---|---|
| `fake` | nothing | 1×1 white PNG; used in all tests |
| `bedrock` | `OKA_IMAGE_MODEL`, `OKA_IMAGE_AWS_REGION` or `AWS_REGION`, `boto3` | AWS Bedrock Stability AI, Nova Canvas, or Titan Image |

This command does **not** open Keynote. Use `oka render-storybook --images` to insert the PNGs into Keynote slides.

## Keynote Roadmap

The next project direction is an interactive Keynote agent:

1. ✅ Interactive agent runtime with session state, planner, executor, tool registry, observations, and step-by-step logs.
2. ✅ Keynote AppleScript adapter (`keynote.*` tools, `oka session --tools keynote`).
3. ✅ Theme and layout discovery (`keynote.list_themes`, `keynote.list_layouts`, `keynote.resolve_layout`).
4. ✅ Object tools (`keynote.add_text_box`, `keynote.add_emoji_text`, `keynote.add_shape`, `keynote.move_object`, `keynote.resize_object`).
5. ✅ Deck spec planner (`oka deck-plan`, `DeckSpec`, `plan_deck_spec`, `render_deck_outline`).
6. ✅ Storybook renderer (`oka render-storybook`, `render_storybook_deck`, deterministic layout templates).
7. ✅ Image asset generation (`oka generate-images`, `generate_image_assets`, `FakeImageProvider`, `BedrockImageProvider`).
8. ✅ Image prompt director (`build_directed_image_prompt`, style modes, `--dry-run`, `--slides`).
9. ✅ Image assets to storybook renderer (`keynote.add_image`, `load_image_assets`, `render-storybook --images`, emoji/shape fallback for missing slides).
10. ✅ Readable storybook text overlays (`renderers/overlays.py`, `build_overlay_plan`, image-aware color and region selection via Pillow).
11. Expose session events through an API suitable for a future Studio UI.
