from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from open_keynote_agent.deck.schema import DeckSpec
from open_keynote_agent.llm.base import LLMClient


def plan_deck_spec(
    brief: str,
    llm_client: LLMClient,
    *,
    slide_count_hint: int | None = None,
    theme_hint: str | None = "Parchment",
) -> DeckSpec:
    if not brief.strip():
        raise ValueError("brief must not be blank")
    if slide_count_hint is not None and not (1 <= slide_count_hint <= 20):
        raise ValueError(f"slide_count_hint must be between 1 and 20, got {slide_count_hint}")

    system_lines = [
        "You are a Keynote deck planner. Return only valid JSON that matches the provided schema.",
        "Guidelines:",
        "- Include a visual description for every slide.",
        "- Use emoji and conceptual decorations when the brief requests visual elements.",
        "- Keep slide text concise and readable for the target audience.",
        "- Prefer warm, story-friendly styles for children's storybook decks.",
        "- Avoid styles explicitly rejected by the brief (e.g. blue business styling).",
        "- Infer the deck language from the primary language used in the brief.",
        "- Slide indexes must be sequential integers starting at 1, not 0.",
    ]
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

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": "\n".join(system_lines)},
        {"role": "user", "content": brief},
    ]

    schema = DeckSpec.model_json_schema()
    raw = llm_client.complete_json(messages, schema)

    try:
        return DeckSpec.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"LLM response did not match DeckSpec schema: {exc}") from exc
