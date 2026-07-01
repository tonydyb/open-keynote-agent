from __future__ import annotations

from open_keynote_agent.deck.schema import DeckSpec
from open_keynote_agent.images.director import DEFAULT_STYLE_MODE, build_directed_image_prompt
from open_keynote_agent.images.schema import ImageSpec, SlideArtSpec

# Exported for test introspection only — director owns the canonical definition.
from open_keynote_agent.images.director import _NO_TEXT_INSTRUCTION  # noqa: F401


def build_slide_art_specs(
    deck: DeckSpec,
    *,
    slide_indexes: set[int] | None = None,
    style_mode: str = DEFAULT_STYLE_MODE,
) -> list[SlideArtSpec]:
    """Return one SlideArtSpec per slide. Deterministic — no LLM called."""
    if slide_indexes is not None:
        available = {slide.index for slide in deck.slides}
        missing = sorted(slide_indexes - available)
        if missing:
            available_range = f"1-{max(available)}" if available else "none"
            raise ValueError(
                f"slide {missing[0]} does not exist in deck; available slides: {available_range}"
            )

    specs: list[SlideArtSpec] = []
    for slide in deck.slides:
        if slide_indexes is not None and slide.index not in slide_indexes:
            continue
        directed = build_directed_image_prompt(deck, slide, style_mode=style_mode)
        specs.append(SlideArtSpec(
            slide_index=slide.index,
            slide_title=slide.title,
            image=ImageSpec(
                prompt=directed.prompt,
                negative_prompt=directed.negative_prompt,
                style=style_mode,
            ),
        ))
    return specs
