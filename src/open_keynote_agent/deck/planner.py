from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from open_keynote_agent.deck.schema import DeckPlanBundle, DeckSpec
from open_keynote_agent.llm.base import LLMClient


def _validate_inputs(brief: str, slide_count_hint: int | None) -> None:
    if not brief.strip():
        raise ValueError("brief must not be blank")
    if slide_count_hint is not None and not (1 <= slide_count_hint <= 20):
        raise ValueError(f"slide_count_hint must be between 1 and 20, got {slide_count_hint}")


def _build_system_lines(
    *,
    slide_count_hint: int | None,
    theme_hint: str | None,
    bilingual: bool,
) -> list[str]:
    output_name = "DeckPlanBundle" if bilingual else "DeckSpec"
    system_lines = [
        f"You are a Keynote deck planner. Return only valid JSON that matches the provided {output_name} schema.",
        "Guidelines:",
        "- Include a visual description for every slide.",
        "- Use emoji and conceptual decorations when the brief requests visual elements.",
        "- Keep slide text concise and readable for the target audience.",
        "- Prefer warm, story-friendly styles for children's storybook decks.",
        "- Avoid styles explicitly rejected by the brief (e.g. blue business styling).",
        "- Infer the deck language from the primary language used in the brief.",
        "- Slide indexes must be sequential integers starting at 1, not 0.",
        "- Slide kind must be exactly one of: cover, characters, chapter, content, climax, lesson, ending. Do not invent other kind values.",
    ]
    if bilingual:
        system_lines.extend([
            "- Return two decks: localized and english.",
            "- The localized deck is for reader-visible text in the brief's primary language.",
            "- The english deck is the image-generation and multilingual source of truth.",
            "- The english deck must use English for title, subtitle, slide titles, body, style, and visual descriptions.",
            "- The english deck's visual.description must be a complete, concrete English visual prompt for the scene.",
            "- Each english visual.description must name the subject, characters, setting, action, and style; do not rely on non-English story names or emoji.",
            "- Keep localized and english slide counts, slide indexes, and slide kinds identical.",
            "- Set localized.content_language to the localized deck language, and english.content_language to 'en'.",
            "- Set both source_language fields to the brief's primary language.",
        ])
    if theme_hint:
        system_lines.append(
            f"- Prefer the built-in Keynote theme '{theme_hint}' unless the brief requests otherwise."
        )
    if slide_count_hint is not None:
        system_lines.append(f"- Produce exactly {slide_count_hint} slides.")
    else:
        system_lines.append(
            "- Respect the requested slide count or range mentioned in the brief."
        )
    return system_lines


def _messages(brief: str, system_lines: list[str]) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": "\n".join(system_lines)},
        {"role": "user", "content": brief},
    ]


def plan_deck_spec(
    brief: str,
    llm_client: LLMClient,
    *,
    slide_count_hint: int | None = None,
    theme_hint: str | None = "Parchment",
) -> DeckSpec:
    _validate_inputs(brief, slide_count_hint)
    messages = _messages(
        brief,
        _build_system_lines(
            slide_count_hint=slide_count_hint,
            theme_hint=theme_hint,
            bilingual=False,
        ),
    )

    schema = DeckSpec.model_json_schema()
    raw = llm_client.complete_json(messages, schema)

    try:
        return DeckSpec.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"LLM response did not match DeckSpec schema: {exc}") from exc


def plan_deck_bundle(
    brief: str,
    llm_client: LLMClient,
    *,
    slide_count_hint: int | None = None,
    theme_hint: str | None = "Parchment",
) -> DeckPlanBundle:
    _validate_inputs(brief, slide_count_hint)
    messages = _messages(
        brief,
        _build_system_lines(
            slide_count_hint=slide_count_hint,
            theme_hint=theme_hint,
            bilingual=True,
        ),
    )

    schema = DeckPlanBundle.model_json_schema()
    raw = llm_client.complete_json(messages, schema)

    try:
        if "localized" not in raw and "english" not in raw:
            deck = DeckSpec.model_validate(raw)
            return DeckPlanBundle(localized=deck, english=deck)
        return DeckPlanBundle.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"LLM response did not match DeckPlanBundle schema: {exc}") from exc
