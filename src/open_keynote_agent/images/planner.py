from __future__ import annotations

from open_keynote_agent.deck.schema import DeckSpec, SlideSpec
from open_keynote_agent.images.schema import ImageSpec, SlideArtSpec

_NO_TEXT_INSTRUCTION = "No text, no captions, no letters, no watermark."
_STORY_MATCH_INSTRUCTION = (
    "Main requirement: create an illustration that directly matches this story and this slide. "
    "The main characters, setting, and events must come from the story title, slide title, "
    "body, and visual description; do not invent an unrelated classroom, family meal, "
    "document, or poster scene."
)

_EMOJI_WORDS = {
    "🐷": "pig",
    "🐖": "pig",
    "🐺": "wolf",
    "🏠": "house",
    "🏡": "cozy house",
    "🧱": "bricks",
    "🌾": "straw",
    "🪵": "wood logs",
    "🌲": "forest trees",
    "🌳": "tree",
    "🌱": "grass",
    "🌻": "sunflower",
    "🌸": "flower",
    "🌹": "rose",
    "🌈": "rainbow",
    "⭐": "star",
    "🌟": "glowing star",
    "✨": "sparkles",
    "💫": "magical sparkle",
    "🌙": "moon",
    "☀️": "sun",
    "🌅": "sunset",
    "❄️": "snowflake",
    "⛄": "snowman",
    "🏰": "castle",
    "👑": "crown",
    "👸": "princess",
    "🤴": "prince",
    "🧙": "wizard",
    "🧚": "fairy",
    "🧞": "genie",
    "🪞": "magic mirror",
    "🍎": "apple",
    "🐢": "turtle",
    "🐇": "rabbit",
    "🦆": "duck",
    "🦢": "swan",
    "🐻": "bear",
    "🦊": "fox",
    "🐵": "monkey",
    "🐦": "bird",
    "🕊️": "dove",
    "💨": "strong wind",
    "🌪️": "whirlwind",
    "⚡": "lightning",
    "🔥": "fire",
    "💧": "water",
    "🎉": "celebration",
    "💕": "warm love",
    "❤️": "heart",
    "💭": "dream bubble",
}


def _emoji_words(emoji: list[str]) -> list[str]:
    words: list[str] = []
    for item in emoji:
        word = _EMOJI_WORDS.get(item.strip())
        if word:
            words.append(word)
    return words


def _build_negative_prompt(deck: DeckSpec) -> str | None:
    negative: list[str] = [
        "text",
        "caption",
        "letters",
        "words",
        "watermark",
        "logo",
        "signature",
        "unrelated classroom",
        "teacher giving a lesson",
        "school worksheet",
        "restaurant",
        "dining table",
        "document",
        "poster",
        "user interface",
        "photorealistic adult realism",
    ]
    negative.extend(deck.style.avoid)
    return ", ".join(negative) if negative else None


def _build_prompt(deck: DeckSpec, slide: SlideSpec) -> str:
    parts: list[str] = []

    # Deck-level context
    parts.append("Create a visual image for this story slide.")
    deck_line = f'Story: "{deck.title}".'
    if deck.subtitle:
        deck_line += f' Subtitle: "{deck.subtitle}".'
    parts.append(deck_line)
    parts.append(_STORY_MATCH_INSTRUCTION)

    # Style / audience
    style_parts: list[str] = [deck.style.mood]
    if deck.style.audience:
        style_parts.append(f"audience: {deck.style.audience}")
    if deck.style.typography:
        style_parts.append(f"typography: {deck.style.typography}")
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
    parts.append("Scene description: " + " ".join(scene_parts))

    # Emoji hints
    emoji_words = _emoji_words(visual.emoji)
    if emoji_words:
        parts.append("Visual objects: " + ", ".join(emoji_words) + ".")

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
            image=ImageSpec(prompt=prompt, negative_prompt=_build_negative_prompt(deck)),
        ))
    return specs
