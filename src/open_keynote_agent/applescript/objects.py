from __future__ import annotations

import re

OBJECT_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

SHAPE_MAP: dict[str, str] = {
    "rectangle": "shape",
}


def validate_object_id(object_id: str) -> None:
    if not OBJECT_ID_PATTERN.match(object_id):
        raise ValueError(
            f"Invalid object_id {object_id!r}. Must match ^[a-z][a-z0-9_]{{0,63}}$."
        )


def peek_object_id(slide: int, kind: str, context: dict) -> str:
    """Return the next candidate object ID without writing the counter to context."""
    kn = context.get("keynote", {})
    counters = kn.get("object_counters", {})
    counter_key = f"slide_{slide:02d}_{kind}"
    n = counters.get(counter_key, 0) + 1
    return f"slide_{slide:02d}_{kind}_{n}"


def commit_object_id(slide: int, kind: str, context: dict) -> None:
    """Advance the counter for (slide, kind). Call only after the runner succeeds."""
    kn = context.setdefault("keynote", {})
    counters = kn.setdefault("object_counters", {})
    counter_key = f"slide_{slide:02d}_{kind}"
    counters[counter_key] = counters.get(counter_key, 0) + 1


def generate_object_id(slide: int, kind: str, context: dict) -> str:
    """Peek the next ID without committing. Use commit_object_id after runner success."""
    return peek_object_id(slide, kind, context)


def validate_geometry(
    slide: int,
    x: float,
    y: float,
    width: float,
    height: float,
    slide_count: int | None = None,
) -> None:
    if slide < 1:
        raise ValueError(f"slide must be >= 1, got {slide}.")
    if slide_count is not None and slide > slide_count:
        raise ValueError(f"slide {slide} exceeds known slide_count {slide_count}.")
    if x < 0:
        raise ValueError(f"x must be >= 0, got {x}.")
    if y < 0:
        raise ValueError(f"y must be >= 0, got {y}.")
    if width <= 0:
        raise ValueError(f"width must be > 0, got {width}.")
    if height <= 0:
        raise ValueError(f"height must be > 0, got {height}.")


def hex_to_rgb_tuple(hex_color: str) -> tuple[int, int, int]:
    """Convert #RRGGBB to a Keynote 0..65535 RGB tuple."""
    if (
        not isinstance(hex_color, str)
        or len(hex_color) != 7
        or hex_color[0] != "#"
    ):
        raise ValueError(f"Invalid hex color {hex_color!r}. Expected #RRGGBB.")
    try:
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
    except ValueError:
        raise ValueError(f"Invalid hex color {hex_color!r}. Expected #RRGGBB.")
    return (
        round(r * 65535 / 255),
        round(g * 65535 / 255),
        round(b * 65535 / 255),
    )
