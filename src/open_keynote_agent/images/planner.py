from __future__ import annotations

from open_keynote_agent.deck.schema import DeckSpec, SlideSpec
from open_keynote_agent.images.schema import ImageSpec, SlideArtSpec

_NO_TEXT_INSTRUCTION = "No text, no captions, no letters, no watermark."


def _build_prompt(deck: DeckSpec, slide: SlideSpec) -> str:
    parts: list[str] = []

    # Deck-level context
    deck_line = f'Children\'s storybook watercolor illustration for "{deck.title}".'
    if deck.subtitle:
        deck_line += f' Subtitle: "{deck.subtitle}".'
    parts.append(deck_line)

    # Style / audience
    style_parts: list[str] = [deck.style.mood]
    if deck.style.audience:
        style_parts.append(f"audience: {deck.style.audience}")
    parts.append("Style: " + "; ".join(style_parts) + ".")

    # Slide-level context
    slide_line = f"Slide {slide.index}: {slide.title}."
    if slide.subtitle:
        slide_line += f" ({slide.subtitle})"
    parts.append(slide_line)

    # Scene description
    visual = slide.visual
    scene_parts: list[str] = [visual.description]
    if slide.body:
        scene_parts.append("Scene includes: " + "; ".join(slide.body) + ".")
    parts.append("Scene: " + " ".join(scene_parts))

    # Emoji hints
    if visual.emoji:
        parts.append("Include: " + " ".join(visual.emoji) + ".")

    # Decorations
    if visual.decorations:
        parts.append("Visual style notes: " + ", ".join(visual.decorations) + ".")

    # Palette from style
    if deck.style.palette:
        parts.append("Palette: " + ", ".join(deck.style.palette) + ".")

    # Hard constraint
    parts.append(_NO_TEXT_INSTRUCTION)

    return " ".join(parts)


def build_slide_art_specs(deck: DeckSpec) -> list[SlideArtSpec]:
    """Return one SlideArtSpec per slide. Deterministic — no LLM called."""
    specs: list[SlideArtSpec] = []
    for slide in deck.slides:
        prompt = _build_prompt(deck, slide)
        specs.append(SlideArtSpec(
            slide_index=slide.index,
            slide_title=slide.title,
            image=ImageSpec(prompt=prompt),
        ))
    return specs
