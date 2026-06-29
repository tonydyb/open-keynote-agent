# Proposal: Add Image Asset Generation

## Summary

Add an image asset generation stage that converts a validated `DeckSpec` into per-slide illustration prompts and PNG files saved under a run output directory.

This change does not touch Keynote. It prepares the visual assets needed for a future illustrated storybook renderer.

```text
DeckSpec JSON
  -> SlideArtSpec / ImageSpec
  -> ImageProvider
  -> .runs/.../assets/slide_01.png
  -> image_manifest.json
```

## Motivation

009 proved that `DeckSpec -> Keynote -> PDF` works, but the visual quality is limited because the renderer only has text, emoji, and rectangle decorations.

To approach the quality of children's storybook examples, the system needs generated illustrations. Those illustrations should be planned and cached before Keynote rendering so failures, costs, and retries are isolated from Keynote automation.

## Goals

- Define `ImageSpec` and `SlideArtSpec`.
- Generate one illustration prompt per `SlideSpec`.
- Add an `ImageProvider` abstraction.
- Implement a deterministic `FakeImageProvider` for tests.
- Implement `BedrockImageProvider` as the primary explicit real provider.
- Optionally support `OpenAIImageProvider` as a secondary provider.
- Save PNG assets under `.runs/.../assets/slide_01.png`.
- Write an `image_manifest.json`.
- Cache generated assets and avoid regenerating unchanged prompts.
- Add a CLI command that generates assets from `deck_spec.json`.
- Keep tests independent of real image APIs, Keynote, and macOS Automation.

## Non-Goals

- Do not insert images into Keynote in this change.
- Do not render Keynote slides.
- Do not call `keynote.*` tools.
- Do not require a real image API for tests.
- Do not solve cross-slide character consistency fully yet.
- Do not implement image editing, inpainting, or upscaling.
- Do not add frontend GUI.

## User Story

Given a deck plan:

```bash
uv run oka deck-plan "请为我制作一个关于《三只小猪》的 8 页童话绘本风 Keynote" --slides 8 --output /tmp/three-pigs-plan
```

Generate image assets:

```bash
uv run oka generate-images /tmp/three-pigs-plan/deck_spec.json --output /tmp/three-pigs-art
```

For real generation, use Bedrock:

```bash
OKA_IMAGE_PROVIDER=bedrock OKA_IMAGE_MODEL=<bedrock-image-model-id> \
  uv run oka generate-images /tmp/three-pigs-plan/deck_spec.json --output /tmp/three-pigs-art
```

The command writes:

```text
/tmp/three-pigs-art/
  art_spec.json
  image_manifest.json
  assets/
    slide_01.png
    slide_02.png
    ...
```

Future renderer changes can consume these PNGs and insert them into Keynote.

## Success Criteria

- A valid `DeckSpec` can produce one `SlideArtSpec` per slide.
- Each slide art spec includes a deterministic `ImageSpec`.
- Fake provider generates valid local PNG files.
- Bedrock provider can generate PNG files when configured with AWS credentials, region, model access, and `OKA_IMAGE_MODEL`.
- Existing files are reused when prompt/config hash matches.
- Manifest records prompt, provider, hash, asset path, and cache status.
- Unit tests run without network, API keys, Keynote, or macOS Automation.
