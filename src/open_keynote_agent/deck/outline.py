from __future__ import annotations

from open_keynote_agent.deck.schema import DeckSpec


def render_deck_outline(deck: DeckSpec) -> str:
    lines: list[str] = []

    lines.append(f"# {deck.title}")
    if deck.subtitle:
        lines.append(f"_{deck.subtitle}_")
    lines.append("")

    if deck.theme:
        lines.append(f"Theme: {deck.theme}")
    lines.append(f"Style: {deck.style.mood}")
    if deck.style.audience:
        lines.append(f"Audience: {deck.style.audience}")
    lines.append("")
    lines.append("## Slides")
    lines.append("")

    for slide in deck.slides:
        kind_label = slide.kind.capitalize()
        lines.append(f"{slide.index}. {kind_label} — {slide.title}")

        if slide.subtitle:
            lines.append(f"   _{slide.subtitle}_")

        if slide.body:
            lines.append("   Body:")
            for bullet in slide.body:
                lines.append(f"   - {bullet}")

        visual = slide.visual
        emoji_part = " ".join(visual.emoji) if visual.emoji else ""
        visual_line = f"   Visual: {visual.description}"
        if emoji_part:
            visual_line = f"   Visual: {emoji_part} — {visual.description}"
        lines.append(visual_line)

        if visual.decorations:
            lines.append(f"   Decorations: {', '.join(visual.decorations)}")

        if slide.layout_hint:
            lines.append(f"   Layout: {slide.layout_hint}")

        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
