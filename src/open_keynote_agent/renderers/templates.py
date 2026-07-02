"""Deterministic storybook layout templates for the 009 renderer.

All coordinates are in Keynote points on a 1280x720 canvas.
Templates never ask the LLM for coordinates — every value is a constant or
a simple deterministic expression.
"""
from __future__ import annotations

from pathlib import Path

from open_keynote_agent.agent.session import ProposedToolCall
from open_keynote_agent.deck.schema import SlideSpec

# ---------------------------------------------------------------------------
# Canvas constants (16:9, 1920x1080)
# ---------------------------------------------------------------------------
W = 1280   # Keynote default canvas width in points (1280x720 = 16:9)
H = 720    # Keynote default canvas height in points

MARGIN = 60

# Body text box
BODY_X = MARGIN
BODY_Y = 220
BODY_W = W // 2 - MARGIN * 2
BODY_H = H - BODY_Y - MARGIN

# Subtitle / secondary text
SUBTITLE_X = MARGIN
SUBTITLE_Y = 120
SUBTITLE_W = W - MARGIN * 2
SUBTITLE_H = 80

# Emoji cluster — right side
EMOJI_RIGHT_X = W // 2 + 80
EMOJI_RIGHT_Y = 160
EMOJI_SPACING = 120

# Emoji cluster — left side (alternating)
EMOJI_LEFT_X = MARGIN + 20
EMOJI_LEFT_Y = 200

# Decorative panel (rectangle) — right column backdrop
PANEL_X = W // 2 + 40
PANEL_Y = MARGIN
PANEL_W = W // 2 - MARGIN * 2
PANEL_H = H - MARGIN * 2

# Large cover emoji
COVER_EMOJI_X = W // 2 + 80
COVER_EMOJI_Y = 180
COVER_EMOJI_SIZE = 120

# Ending
ENDING_EMOJI_X = W // 2 - 80
ENDING_EMOJI_Y = H // 2 - 60
ENDING_EMOJI_SIZE = 110

# Font sizes
FONT_SUBTITLE = 36
FONT_BODY = 28
FONT_EMOJI_DEFAULT = 80
FONT_CLIMAX_TITLE_HINT = 64  # used as body/subtitle font size for climax
FONT_OVERLAY_BODY = 34
FONT_OVERLAY_SUBTITLE = 38

# Semantic layout map: SlideSpec.kind -> semantic layout name
LAYOUT_FOR_KIND: dict[str, str] = {
    "cover": "title",
    "characters": "title_body",
    "chapter": "title_body",
    "climax": "title_body",
    "lesson": "title_body",
    "ending": "title",
    "content": "title_body",
}

# Fallback emoji per slide kind when visual.emoji is empty
FALLBACK_EMOJI: dict[str, str] = {
    "cover": "📖",
    "characters": "🐷",
    "climax": "🐺",
    "ending": "✨",
}
FALLBACK_EMOJI_DEFAULT = "⭐"


def _oid(slide_index: int, role: str) -> str:
    return f"slide_{slide_index:02d}_{role}"


def _emoji_calls(
    slide_index: int,
    emojis: list[str],
    x0: float,
    y0: float,
    size: float,
    spacing: float,
) -> list[ProposedToolCall]:
    calls = []
    for n, emoji in enumerate(emojis[:4], start=1):
        oid = _oid(slide_index, f"emoji_{n}")
        calls.append(ProposedToolCall(
            tool="keynote.add_emoji_text",
            args={
                "slide": slide_index,
                "emoji": emoji,
                "x": x0 + (n - 1) * spacing,
                "y": y0,
                "size": size,
                "object_id": oid,
            },
            description=f"Add emoji {emoji} on slide {slide_index}",
        ))
    return calls


def _get_emojis(slide: SlideSpec) -> list[str]:
    if slide.visual.emoji:
        return list(slide.visual.emoji[:4])
    fallback = FALLBACK_EMOJI.get(slide.kind, FALLBACK_EMOJI_DEFAULT)
    return [fallback]


def calls_for_slide(slide: SlideSpec) -> list[ProposedToolCall]:
    """Return deterministic template tool calls for a single slide.

    Does not include add_slide or set_slide_title — those are handled by
    the renderer to keep slide-number tracking clean.
    """
    kind = slide.kind
    idx = slide.index

    if kind == "cover":
        return _cover_calls(slide, idx)
    if kind == "characters":
        return _characters_calls(slide, idx)
    if kind == "chapter":
        return _chapter_calls(slide, idx)
    if kind == "climax":
        return _climax_calls(slide, idx)
    if kind == "lesson":
        return _lesson_calls(slide, idx)
    if kind == "ending":
        return _ending_calls(slide, idx)
    # content and unknown kinds
    return _content_calls(slide, idx)


def _cover_calls(slide: SlideSpec, idx: int) -> list[ProposedToolCall]:
    calls: list[ProposedToolCall] = []
    # Decorative panel — added first so emoji and text render in front of it
    calls.append(ProposedToolCall(
        tool="keynote.add_shape",
        args={
            "slide": idx,
            "shape": "rectangle",
            "x": PANEL_X,
            "y": PANEL_Y,
            "width": PANEL_W,
            "height": PANEL_H,
            "object_id": _oid(idx, "panel"),
        },
        description=f"Add decoration panel on slide {idx}",
    ))
    # Subtitle text box
    if slide.subtitle:
        calls.append(ProposedToolCall(
            tool="keynote.add_text_box",
            args={
                "slide": idx,
                "text": slide.subtitle,
                "x": SUBTITLE_X,
                "y": SUBTITLE_Y,
                "width": SUBTITLE_W,
                "height": SUBTITLE_H,
                "font_size": FONT_SUBTITLE,
                "object_id": _oid(idx, "subtitle"),
            },
            description=f"Add subtitle on slide {idx}",
        ))
    # Emoji cluster — large, right side
    emojis = _get_emojis(slide)
    calls += _emoji_calls(
        idx, emojis,
        x0=COVER_EMOJI_X, y0=COVER_EMOJI_Y,
        size=COVER_EMOJI_SIZE, spacing=COVER_EMOJI_SIZE + 20,
    )
    return calls


def _characters_calls(slide: SlideSpec, idx: int) -> list[ProposedToolCall]:
    calls: list[ProposedToolCall] = []
    # Body text block
    if slide.body:
        text = "\n".join(f"• {b}" for b in slide.body)
        calls.append(ProposedToolCall(
            tool="keynote.add_text_box",
            args={
                "slide": idx,
                "text": text,
                "x": BODY_X,
                "y": BODY_Y,
                "width": BODY_W,
                "height": BODY_H,
                "font_size": FONT_BODY,
                "object_id": _oid(idx, "body"),
            },
            description=f"Add body text on slide {idx}",
        ))
    # Up to 3 emoji in a row on the right side
    emojis = _get_emojis(slide)[:3]
    calls += _emoji_calls(
        idx, emojis,
        x0=EMOJI_RIGHT_X, y0=EMOJI_RIGHT_Y,
        size=FONT_EMOJI_DEFAULT, spacing=EMOJI_SPACING,
    )
    return calls


def _chapter_calls(slide: SlideSpec, idx: int) -> list[ProposedToolCall]:
    """Chapter: alternates emoji left/right by slide index."""
    calls: list[ProposedToolCall] = []
    if slide.body:
        text = "\n".join(f"• {b}" for b in slide.body)
        body_x = BODY_X if idx % 2 == 0 else W // 2 + 40
        calls.append(ProposedToolCall(
            tool="keynote.add_text_box",
            args={
                "slide": idx,
                "text": text,
                "x": body_x,
                "y": BODY_Y,
                "width": BODY_W,
                "height": BODY_H,
                "font_size": FONT_BODY,
                "object_id": _oid(idx, "body"),
            },
            description=f"Add body text on slide {idx}",
        ))
    emojis = _get_emojis(slide)
    emoji_x = EMOJI_LEFT_X if idx % 2 == 0 else EMOJI_RIGHT_X
    calls += _emoji_calls(
        idx, emojis,
        x0=emoji_x, y0=EMOJI_RIGHT_Y,
        size=FONT_EMOJI_DEFAULT, spacing=EMOJI_SPACING,
    )
    return calls


def _climax_calls(slide: SlideSpec, idx: int) -> list[ProposedToolCall]:
    calls: list[ProposedToolCall] = []
    if slide.body:
        text = "\n".join(f"• {b}" for b in slide.body)
        calls.append(ProposedToolCall(
            tool="keynote.add_text_box",
            args={
                "slide": idx,
                "text": text,
                "x": BODY_X,
                "y": BODY_Y,
                "width": BODY_W,
                "height": BODY_H,
                "font_size": FONT_CLIMAX_TITLE_HINT,
                "object_id": _oid(idx, "body"),
            },
            description=f"Add climax body on slide {idx}",
        ))
    emojis = _get_emojis(slide)
    calls += _emoji_calls(
        idx, emojis,
        x0=EMOJI_RIGHT_X, y0=EMOJI_RIGHT_Y,
        size=FONT_EMOJI_DEFAULT + 20, spacing=EMOJI_SPACING,
    )
    return calls


def _lesson_calls(slide: SlideSpec, idx: int) -> list[ProposedToolCall]:
    calls: list[ProposedToolCall] = []
    if slide.body:
        text = "\n".join(f"• {b}" for b in slide.body)
        calls.append(ProposedToolCall(
            tool="keynote.add_text_box",
            args={
                "slide": idx,
                "text": text,
                "x": BODY_X,
                "y": BODY_Y,
                "width": W - MARGIN * 2,
                "height": BODY_H,
                "font_size": FONT_BODY,
                "object_id": _oid(idx, "body"),
            },
            description=f"Add lesson body on slide {idx}",
        ))
    emojis = _get_emojis(slide)
    calls += _emoji_calls(
        idx, emojis,
        x0=EMOJI_RIGHT_X, y0=EMOJI_RIGHT_Y,
        size=FONT_EMOJI_DEFAULT, spacing=EMOJI_SPACING,
    )
    return calls


def _ending_calls(slide: SlideSpec, idx: int) -> list[ProposedToolCall]:
    calls: list[ProposedToolCall] = []
    if slide.body:
        text = "\n".join(slide.body)
        calls.append(ProposedToolCall(
            tool="keynote.add_text_box",
            args={
                "slide": idx,
                "text": text,
                "x": SUBTITLE_X,
                "y": SUBTITLE_Y,
                "width": SUBTITLE_W,
                "height": SUBTITLE_H,
                "font_size": FONT_SUBTITLE,
                "object_id": _oid(idx, "subtitle"),
            },
            description=f"Add ending text on slide {idx}",
        ))
    emojis = _get_emojis(slide)
    calls += _emoji_calls(
        idx, emojis,
        x0=ENDING_EMOJI_X, y0=ENDING_EMOJI_Y,
        size=ENDING_EMOJI_SIZE, spacing=ENDING_EMOJI_SIZE + 20,
    )
    return calls


def _content_calls(slide: SlideSpec, idx: int) -> list[ProposedToolCall]:
    calls: list[ProposedToolCall] = []
    if slide.body:
        text = "\n".join(f"• {b}" for b in slide.body)
        calls.append(ProposedToolCall(
            tool="keynote.add_text_box",
            args={
                "slide": idx,
                "text": text,
                "x": BODY_X,
                "y": BODY_Y,
                "width": BODY_W,
                "height": BODY_H,
                "font_size": FONT_BODY,
                "object_id": _oid(idx, "body"),
            },
            description=f"Add body text on slide {idx}",
        ))
    emojis = _get_emojis(slide)
    calls += _emoji_calls(
        idx, emojis,
        x0=EMOJI_RIGHT_X, y0=EMOJI_RIGHT_Y,
        size=FONT_EMOJI_DEFAULT, spacing=EMOJI_SPACING,
    )
    return calls


# ---------------------------------------------------------------------------
# Image frame constants (1280x720 canvas)
# ---------------------------------------------------------------------------

# Full-bleed image frame for image-backed storybook pages.
IMAGE_FULL_X = 0
IMAGE_FULL_Y = 0
IMAGE_FULL_W = W
IMAGE_FULL_H = H

# Deterministic overlay text frame. Later changes can add visual analysis,
# text panels, shadows, or alternate positions.
OVERLAY_TEXT_X = 90
OVERLAY_TEXT_Y = 500
OVERLAY_TEXT_W = W - OVERLAY_TEXT_X * 2
OVERLAY_TEXT_H = 170


def image_call_for_slide(slide: SlideSpec, image_path: Path) -> ProposedToolCall:
    """Return the deterministic keynote.add_image call for a slide's image asset."""
    idx = slide.index

    return ProposedToolCall(
        tool="keynote.add_image",
        args={
            "slide": idx,
            "path": str(image_path),
            "x": IMAGE_FULL_X,
            "y": IMAGE_FULL_Y,
            "width": IMAGE_FULL_W,
            "height": IMAGE_FULL_H,
            "object_id": _oid(idx, "art"),
        },
        description=f"Insert illustration on slide {idx}",
    )


def calls_for_slide_image_overlay(slide: SlideSpec, image_path: Path) -> list[ProposedToolCall]:
    """Return text overlay calls for an image-backed slide using 013 overlay planning.

    Analyses candidate regions in the image to choose the best text position
    and font color. Falls back to fixed 012 overlay frame if analysis fails.
    """
    from open_keynote_agent.renderers.overlays import build_overlay_plan  # noqa: PLC0415

    plan = build_overlay_plan(slide, image_path)
    idx = slide.index

    if not plan.text:
        return []

    r = plan.region
    s = plan.style

    return [ProposedToolCall(
        tool="keynote.add_text_box",
        args={
            "slide": idx,
            "text": plan.text,
            "x": r.x,
            "y": r.y,
            "width": r.width,
            "height": r.height,
            "font_size": s.font_size,
            "font_color": s.text_color,  # hex string, e.g. "#FFFFFF"
            "object_id": _oid(idx, "body"),
        },
        description=f"Add overlay text on slide {idx} ({plan.region.name}, color={s.text_color})",
    )]


def calls_for_slide_text_only(slide: SlideSpec) -> list[ProposedToolCall]:
    """Return only text-related template calls for a slide (no emoji, no decorative shapes).

    Used when an image asset provides the primary visual for the slide.
    """
    kind = slide.kind
    idx = slide.index

    if kind == "cover":
        calls: list[ProposedToolCall] = []
        if slide.subtitle:
            calls.append(ProposedToolCall(
                tool="keynote.add_text_box",
                args={
                    "slide": idx,
                    "text": slide.subtitle,
                    "x": OVERLAY_TEXT_X,
                    "y": OVERLAY_TEXT_Y,
                    "width": OVERLAY_TEXT_W,
                    "height": OVERLAY_TEXT_H,
                    "font_size": FONT_OVERLAY_SUBTITLE,
                    "object_id": _oid(idx, "subtitle"),
                },
                description=f"Add subtitle on slide {idx}",
            ))
        return calls

    calls = []
    text_parts = list(slide.body)
    if not text_parts and slide.subtitle:
        text_parts = [slide.subtitle]
    if not text_parts:
        text_parts = [slide.title]

    text = "\n".join(text_parts)
    calls.append(ProposedToolCall(
        tool="keynote.add_text_box",
        args={
            "slide": idx,
            "text": text,
            "x": OVERLAY_TEXT_X,
            "y": OVERLAY_TEXT_Y,
            "width": OVERLAY_TEXT_W,
            "height": OVERLAY_TEXT_H,
            "font_size": FONT_OVERLAY_BODY,
            "object_id": _oid(idx, "body"),
        },
        description=f"Add overlay text on slide {idx}",
    ))
    return calls
