# Proposal: Add Readable Storybook Text Overlays

## Summary

Improve the image-backed storybook renderer so text placed over full-bleed illustrations remains readable.

012 made generated images the primary visual for Keynote storybook slides. It uses full-bleed images and deterministic overlay text, but the overlay is still naive: text can land on bright, dark, or busy image regions without contrast protection.

013 adds deterministic image-aware overlay planning:

```text
DeckSpec + image_manifest.json/assets
  -> image-aware overlay plan
  -> Keynote storybook with readable text overlays
```

## Motivation

Children's picture books are image-first. The text must feel part of the page, but it must also remain legible on top of varied generated illustrations.

Current 012 output can fail when:

- dark text lands on a dark background
- light text lands on a bright background
- text overlays a character face or important story subject
- the fixed bottom text box covers a busy part of the illustration
- long body text overflows or feels like presentation bullets

013 solves the readability layer without introducing LLM layout decisions.

## Goals

- Analyze the generated image under candidate text regions.
- Automatically choose text color based on background brightness.
- Add a semi-transparent text backing shape when needed.
- Add basic text shadow or outline support where Keynote tooling allows it, or define a deterministic fallback.
- Choose among multiple deterministic storybook overlay templates.
- Prefer regions that are less visually busy and avoid obvious subject-heavy areas when possible.
- Keep the renderer deterministic and testable without Keynote.
- Preserve 012 behavior when image analysis is unavailable or disabled.

## Non-Goals

- Do not generate images.
- Do not call an LLM.
- Do not use a vision model.
- Do not change `DeckSpec`.
- Do not solve print bleed/trim/CMYK.
- Do not perform full object detection or semantic segmentation.
- Do not guarantee perfect subject avoidance for all generated images.
- Do not replace Keynote with Pillow/ReportLab/PPTX.

## User Story

Given:

```bash
uv run oka render-storybook /tmp/cinderella-plan/deck_spec.json \
  --images /tmp/cinderella-art/image_manifest.json \
  --output /tmp/cinderella-keynote
```

The renderer should:

- keep each illustration full-bleed
- put story text over a readable area
- choose white text on dark backgrounds and dark text on bright backgrounds
- add a subtle translucent backing panel when the image region is too busy
- avoid covering the main subject when a better deterministic region is available

## Success Criteria

- Image-backed slides get an overlay plan before Keynote tool calls are emitted.
- Text color is chosen from sampled image brightness.
- Busy regions receive a backing panel or other contrast support.
- The renderer can choose from at least three deterministic template positions.
- Unit tests cover brightness/color decisions, backing panel decisions, template selection, and fallback behavior.
- No tests require real Keynote or cloud credentials.
