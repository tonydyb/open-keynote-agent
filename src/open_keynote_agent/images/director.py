from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

from open_keynote_agent.deck.schema import DeckSpec, SlideSpec

_NO_TEXT_INSTRUCTION = "No text, no captions, no letters, no watermark."

# ---------------------------------------------------------------------------
# Style modes
# ---------------------------------------------------------------------------

# Maps style mode ID → fixed preset description (empty for deck_style).
STYLE_MODES: dict[str, str] = {
    "soft_storybook_watercolor": (
        "gentle hand-painted children's picture-book look, watercolor texture, "
        "soft edges, warm colors, simple composition, non-photorealistic characters"
    ),
    "cute_hand_drawn_cartoon": (
        "cute hand-drawn cartoon picture-book look, rounded simplified characters, "
        "expressive faces, bright friendly colors, clear child-readable shapes"
    ),
    "paper_cut_collage_storybook": (
        "paper-cut collage picture-book look, layered paper texture, simple shapes, "
        "tactile craft materials, playful depth, child-friendly composition"
    ),
    "deck_style": "",  # style comes from DeckSpec / VisualSpec fields
}

DEFAULT_STYLE_MODE = "soft_storybook_watercolor"

_FIXED_PRESET_MODES: frozenset[str] = frozenset(STYLE_MODES) - {"deck_style"}

# Style guardrails — added to negative_prompt for every mode to prevent
# photorealistic / cinematic drift in children's illustration outputs.
_STYLE_GUARDRAILS: list[str] = [
    "not photorealistic",
    "not cinematic",
    "not realistic portrait",
    "not movie still",
    "not 3D render",
    "not adult editorial illustration",
]

# ---------------------------------------------------------------------------
# Noun-phrase extraction helpers
# ---------------------------------------------------------------------------

# Words that terminate a noun phrase scan (prepositions, conjunctions, verbs).
_NP_STOPS = frozenset({
    "a", "an", "the",
    "in", "on", "at", "by", "with", "before", "after", "from", "to",
    "into", "onto", "upon", "inside", "outside", "beside", "behind",
    "above", "below", "between", "through", "across", "towards",
    "and", "or", "but", "nor", "of", "for",
    "who", "that", "which", "when", "where", "while", "as",
    "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may",
    "stands", "walks", "sits", "runs", "looks", "wears", "holds",
    "raises", "points", "turns", "reaches", "gazes", "steps", "floats",
    "wearing", "holding", "standing", "sitting", "walking", "lying",
    "surrounded", "facing", "leaning",
    "this", "their", "his", "her", "its", "our",
})

# ---------------------------------------------------------------------------
# Emoji-to-English object word mapping
# ---------------------------------------------------------------------------

EMOJI_WORDS: dict[str, str] = {
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

# Generic forbidden terms (text/UI artefacts).
_GENERIC_FORBIDDEN = [
    "text",
    "caption",
    "letters",
    "words",
    "watermark",
    "logo",
    "signature",
    "document",
    "poster",
    "user interface",
]

# Composition defaults keyed by slide kind.
_COMPOSITION_FOR_KIND: dict[str, str] = {
    "cover": "centered character, clean background, room for title overlay",
    "characters": "grouped character portrait",
    "chapter": "medium-wide storybook scene",
    "climax": "dramatic medium-wide storybook scene",
    "lesson": "warm closing composition with characters",
    "ending": "warm closing composition, peaceful scene",
    "content": "medium-wide storybook scene",
}

# ---------------------------------------------------------------------------
# Pydantic model
# ---------------------------------------------------------------------------


class DirectedImagePrompt(BaseModel):
    model_config = {"extra": "forbid"}

    slide_index: int = Field(ge=1)
    slide_title: str
    primary_scene: str
    required_subjects: list[str] = Field(default_factory=list)
    forbidden_subjects: list[str] = Field(default_factory=list)
    composition: str | None = None
    style_notes: list[str] = Field(default_factory=list)
    story_context: str | None = None
    prompt: str
    negative_prompt: str | None = None

    @field_validator("slide_title", "primary_scene", "prompt")
    @classmethod
    def nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("field must not be blank")
        return v

    @field_validator("required_subjects", "forbidden_subjects", "style_notes", mode="before")
    @classmethod
    def items_nonempty(cls, v: object) -> object:
        if not isinstance(v, list):
            raise ValueError("must be a list")
        for item in v:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("list items must be non-empty strings")
        return v


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _emoji_subject_words(emoji: list[str]) -> list[str]:
    words: list[str] = []
    for item in emoji:
        word = EMOJI_WORDS.get(item.strip())
        if word and word not in words:
            words.append(word)
    return words


def _extract_noun_phrases(text: str) -> list[str]:
    """Heuristic: extract multi-word noun phrases, breaking on stop words."""
    tokens = re.findall(r"[A-Za-z一-鿿]+(?:'[a-z]+)?", text)
    phrases: list[str] = []
    run: list[str] = []
    for tok in tokens:
        if tok.lower() in _NP_STOPS:
            if len(run) >= 2:
                phrase = " ".join(run)
                if phrase.lower() not in {p.lower() for p in phrases}:
                    phrases.append(phrase)
            run = []
        else:
            run.append(tok)
    if len(run) >= 2:
        phrase = " ".join(run)
        if phrase.lower() not in {p.lower() for p in phrases}:
            phrases.append(phrase)
    return phrases


def _build_required_subjects(slide: SlideSpec) -> list[str]:
    """Conservative extraction of required subjects from SlideSpec data."""
    seen: set[str] = set()
    subjects: list[str] = []

    def _add(term: str) -> None:
        key = term.lower().strip()
        if key and key not in seen:
            seen.add(key)
            subjects.append(term.strip())

    for word in _emoji_subject_words(slide.visual.emoji):
        _add(word)
    for phrase in _extract_noun_phrases(slide.visual.description):
        _add(phrase)
    title_tokens = slide.title.strip().split()
    if len(title_tokens) >= 2:
        _add(slide.title.strip())
    if slide.subtitle:
        for phrase in _extract_noun_phrases(slide.subtitle):
            _add(phrase)
    for bullet in (slide.body or []):
        stripped = bullet.strip()
        if stripped:
            _add(stripped)

    return subjects


def _build_forbidden_subjects(deck: DeckSpec, slide: SlideSpec) -> list[str]:
    """Generic drift exclusions — no story-specific branches."""
    forbidden = list(_GENERIC_FORBIDDEN)

    desc_lower = slide.visual.description.lower()
    title_lower = slide.title.lower()

    if any(w in desc_lower for w in ("alone", "solitary", "by herself", "by himself")):
        forbidden.append("crowd of people")
        forbidden.append("multiple duplicate characters")

    if any(w in desc_lower + title_lower for w in ("royal chamber", "throne room", "ballroom")):
        forbidden.append("outdoor picnic")
        forbidden.append("dining table with food")

    if any(w in desc_lower + title_lower for w in ("forest", "meadow", "outdoor", "outside", "field")):
        forbidden.append("indoor banquet")
        forbidden.append("dining hall")

    return forbidden


def _build_style_notes(deck: DeckSpec, slide: SlideSpec, style_mode: str) -> list[str]:
    """Build Style section notes for the given style mode.

    Fixed preset modes use only their preset description (+ audience).
    deck_style uses DeckSpec / VisualSpec fields exclusively.
    """
    if style_mode in _FIXED_PRESET_MODES:
        notes: list[str] = [f"{style_mode} — {STYLE_MODES[style_mode]}"]
        if deck.style.audience:
            notes.append(f"audience: {deck.style.audience}")
        return notes

    # deck_style: compose from DeckSpec / VisualSpec fields only.
    parts: list[str] = [deck.style.mood]
    if deck.style.audience:
        parts.append(f"audience: {deck.style.audience}")
    if deck.style.typography:
        parts.append(f"typography: {deck.style.typography}")
    if deck.style.palette:
        parts.append("palette: " + ", ".join(deck.style.palette))
    if slide.visual.decorations:
        parts.append("decorations: " + ", ".join(slide.visual.decorations))
    return ["; ".join(parts)]


def _build_primary_scene(slide: SlideSpec) -> str:
    # Lead with visual.description (the concrete scene), not the title.
    # Title follows as secondary label to avoid activating broad story priors.
    parts: list[str] = [slide.visual.description]
    if slide.subtitle:
        parts.append(f"({slide.subtitle})")
    if slide.body:
        parts.append("Includes: " + "; ".join(slide.body) + ".")
    scene_text = " ".join(parts)
    return f"{scene_text} [Slide: {slide.title}]"


def _assemble_prompt(
    primary_scene: str,
    required_subjects: list[str],
    composition: str | None,
    style_notes: list[str],
    story_context: str | None,
    style_mode: str,
) -> str:
    sections: list[str] = []

    if style_mode in _FIXED_PRESET_MODES and style_notes:
        sections.append("Image style, follow strongly:\n" + "\n".join(style_notes))

    sections.append(f"Primary scene, follow exactly:\n{primary_scene}")

    if required_subjects:
        bullet_lines = "\n".join(f"- {s}" for s in required_subjects)
        sections.append(f"Required subjects:\n{bullet_lines}")

    if composition:
        sections.append(f"Composition:\n{composition}")

    if style_notes:
        sections.append("Style:\n" + "\n".join(style_notes))

    if story_context:
        sections.append(
            f"Story context:\n{story_context}. "
            "Use the story only as background context; "
            "do not add unrelated story elements."
        )

    sections.append(_NO_TEXT_INSTRUCTION)

    return "\n\n".join(sections)


# Per-guardrail signal patterns. A guardrail is suppressed when its signal matches
# the style text, meaning the user explicitly requested that visual style.
# Lookbehind (?<!non-) prevents "non-photorealistic" from suppressing "not photorealistic".
_GUARDRAIL_SIGNALS: dict[str, re.Pattern[str]] = {
    "not photorealistic": re.compile(r"(?<!non-)\bphotorealistic\b", re.IGNORECASE),
    "not cinematic": re.compile(r"(?<!non-)\bcinematic\b", re.IGNORECASE),
    "not realistic portrait": re.compile(r"(?<!non-)\brealistic\b", re.IGNORECASE),
    "not movie still": re.compile(r"(?<!non-)\bmovie\b", re.IGNORECASE),
    "not 3D render": re.compile(r"(?<!non-)(?<!\w)\b3[Dd]\b", re.IGNORECASE),
    "not adult editorial illustration": re.compile(r"(?<!non-)\beditor(?:ial)?\b", re.IGNORECASE),
}


def _assemble_negative_prompt(
    forbidden_subjects: list[str],
    avoid: list[str],
    style_text: str = "",
) -> str | None:
    # Order: generic forbidden → style guardrails → user-specified avoid terms.
    # Drop guardrails whose signal word is positively affirmed in style_text
    # (e.g. "cinematic 3D fairy-tale render" in deck_style mood suppresses cinematic and 3D).
    active_guardrails = [
        g for g in _STYLE_GUARDRAILS
        if not _GUARDRAIL_SIGNALS[g].search(style_text)
    ]
    all_terms = list(forbidden_subjects) + active_guardrails + list(avoid)
    if not all_terms:
        return None
    return ", ".join(all_terms)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_directed_image_prompt(
    deck: DeckSpec,
    slide: SlideSpec,
    *,
    style_mode: str = DEFAULT_STYLE_MODE,
) -> DirectedImagePrompt:
    """Return a scene-first, structured image prompt for one slide. Deterministic, no LLM."""
    if style_mode not in STYLE_MODES:
        supported = ", ".join(sorted(STYLE_MODES))
        raise ValueError(f"unknown style mode {style_mode!r}; supported: {supported}")

    primary_scene = _build_primary_scene(slide)
    required_subjects = _build_required_subjects(slide)
    forbidden_subjects = _build_forbidden_subjects(deck, slide)
    composition = _COMPOSITION_FOR_KIND.get(slide.kind, "medium-wide storybook scene")
    style_notes = _build_style_notes(deck, slide, style_mode)

    story_context_line = deck.title
    if deck.subtitle:
        story_context_line += f": {deck.subtitle}"

    prompt = _assemble_prompt(
        primary_scene=primary_scene,
        required_subjects=required_subjects,
        composition=composition,
        style_notes=style_notes,
        story_context=story_context_line,
        style_mode=style_mode,
    )
    negative_prompt = _assemble_negative_prompt(
        forbidden_subjects=forbidden_subjects,
        avoid=deck.style.avoid,
        style_text=" ".join(style_notes),
    )

    return DirectedImagePrompt(
        slide_index=slide.index,
        slide_title=slide.title,
        primary_scene=primary_scene,
        required_subjects=required_subjects,
        forbidden_subjects=forbidden_subjects,
        composition=composition,
        style_notes=style_notes,
        story_context=story_context_line,
        prompt=prompt,
        negative_prompt=negative_prompt,
    )
