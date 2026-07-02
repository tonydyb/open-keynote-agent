"""Deterministic image-aware overlay planning for 013.

Accepts a SlideSpec and an image path, returns an OverlayPlan that specifies:
  - which candidate region to place text in
  - text color (#FFFFFF or #2C1810) based on sampled background luminance
  - whether a backing panel is recommended (use_backing=True in diagnostics)

No LLM and no vision model are used. If Pillow is unavailable or image
analysis fails, returns a deterministic fallback plan identical to 012 behavior.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from pathlib import Path

from open_keynote_agent.deck.schema import SlideSpec

# ---------------------------------------------------------------------------
# Canvas / fallback constants (1280x720)
# ---------------------------------------------------------------------------
_W = 1280
_H = 720

# 012 fixed fallback region
_FALLBACK_X = 90
_FALLBACK_Y = 500
_FALLBACK_W = 1100
_FALLBACK_H = 170
_FALLBACK_FONT_SIZE = 34.0
_FALLBACK_COLOR = "#FFFFFF"

# Luminance threshold
_LUM_THRESHOLD = 128.0
_AMBIGUOUS_LOW = 112.0
_AMBIGUOUS_HIGH = 144.0
# Busyness (stddev of luminance) threshold for recommending backing
_BUSY_THRESHOLD = 45.0

# Text colors
_COLOR_DARK_BG = "#FFFFFF"
_COLOR_LIGHT_BG = "#2C1810"

# Font sizes
_FONT_OVERLAY = 34.0
_FONT_OVERLAY_COVER = 38.0


# ---------------------------------------------------------------------------
# Data models (dataclasses; Pydantic not needed — these stay in-memory only)
# ---------------------------------------------------------------------------

@dataclass
class OverlayRegion:
    name: str
    x: float
    y: float
    width: float
    height: float


@dataclass
class OverlayStyle:
    text_color: str
    font_size: float
    use_backing: bool
    backing_color: str | None = None
    backing_opacity: float | None = None
    shadow: bool = False


@dataclass
class OverlayPlan:
    slide_index: int
    region: OverlayRegion
    style: OverlayStyle
    text: str
    diagnostics: dict[str, float | str | bool] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Candidate regions
# ---------------------------------------------------------------------------

_CANDIDATE_REGIONS: list[OverlayRegion] = [
    OverlayRegion("bottom_band",    x=90,  y=500, width=1100, height=170),
    OverlayRegion("top_band",       x=90,  y=50,  width=1100, height=150),
    OverlayRegion("left_panel",     x=70,  y=120, width=430,  height=480),
    OverlayRegion("right_panel",    x=780, y=120, width=430,  height=480),
    OverlayRegion("center_caption", x=190, y=430, width=900,  height=190),
]

_REGION_BY_NAME: dict[str, OverlayRegion] = {r.name: r for r in _CANDIDATE_REGIONS}

# Slide-kind preferences: ordered list of preferred region names
_KIND_PREFERENCES: dict[str, list[str]] = {
    "cover":      ["bottom_band", "center_caption"],
    "characters": ["bottom_band", "top_band"],
    "chapter":    ["bottom_band"],
    "content":    ["bottom_band"],
    "climax":     ["top_band", "bottom_band"],
    "lesson":     ["left_panel", "right_panel"],
    "ending":     ["bottom_band", "center_caption"],
}
_DEFAULT_PREFERENCES = ["bottom_band"]

# Preference penalty applied to non-preferred regions
_PREFERENCE_PENALTY = 100.0


# ---------------------------------------------------------------------------
# Image analysis helpers
# ---------------------------------------------------------------------------

def _region_metrics(
    pixels: list[float],
) -> tuple[float, float]:
    """Return (mean_luminance, stddev_luminance) for a flat list of Y values."""
    if not pixels:
        return 128.0, 0.0
    mean = sum(pixels) / len(pixels)
    stddev = statistics.pstdev(pixels) if len(pixels) > 1 else 0.0
    return mean, stddev


def _sample_luminance(image_path: Path, region: OverlayRegion) -> tuple[float, float]:
    """Return (mean_luminance, stddev) for the given region in the image.

    Maps 1280x720 Keynote coordinates to image pixel coordinates, crops
    the region, and computes per-pixel luminance using BT.709 weights.
    Raises on any Pillow or file error — callers must handle.
    """
    from PIL import Image  # noqa: PLC0415 — optional dependency

    with Image.open(image_path) as img:
        img_w, img_h = img.size
        # Scale Keynote points to image pixels
        scale_x = img_w / _W
        scale_y = img_h / _H
        px0 = int(region.x * scale_x)
        py0 = int(region.y * scale_y)
        px1 = int((region.x + region.width) * scale_x)
        py1 = int((region.y + region.height) * scale_y)
        # Clamp
        px0 = max(0, min(px0, img_w - 1))
        py0 = max(0, min(py0, img_h - 1))
        px1 = max(px0 + 1, min(px1, img_w))
        py1 = max(py0 + 1, min(py1, img_h))

        cropped = img.crop((px0, py0, px1, py1)).convert("RGB")
        raw = cropped.tobytes()  # flat bytes R,G,B,R,G,B,...

    luminances = [
        0.2126 * raw[i] + 0.7152 * raw[i + 1] + 0.0722 * raw[i + 2]
        for i in range(0, len(raw), 3)
    ]
    return _region_metrics(luminances)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score_region(
    region: OverlayRegion,
    mean_lum: float,
    stddev_lum: float,
    preferred_names: list[str],
) -> float:
    """Lower score is better."""
    busyness = stddev_lum
    # Penalty for being far from preferred positions
    pref_penalty = 0.0 if region.name in preferred_names else _PREFERENCE_PENALTY
    # Center subject penalty: center_caption overlaps the visual focus area
    center_penalty = 20.0 if region.name == "center_caption" else 0.0
    return busyness + pref_penalty + center_penalty


# ---------------------------------------------------------------------------
# Text color selection
# ---------------------------------------------------------------------------

def _choose_color(mean_lum: float) -> str:
    return _COLOR_DARK_BG if mean_lum < _LUM_THRESHOLD else _COLOR_LIGHT_BG


def _needs_backing(mean_lum: float, stddev_lum: float) -> bool:
    ambiguous = _AMBIGUOUS_LOW <= mean_lum <= _AMBIGUOUS_HIGH
    return ambiguous or stddev_lum > _BUSY_THRESHOLD


# ---------------------------------------------------------------------------
# Text extraction (reuse 012 rules, no bullets)
# ---------------------------------------------------------------------------

def _extract_overlay_text(slide: SlideSpec) -> str:
    if slide.kind == "cover":
        if slide.subtitle:
            return slide.subtitle
        return ""
    text_parts = list(slide.body)
    if not text_parts and slide.subtitle:
        text_parts = [slide.subtitle]
    if not text_parts:
        text_parts = [slide.title]
    return "\n".join(text_parts)


# ---------------------------------------------------------------------------
# Fallback plan (012-compatible, no image analysis)
# ---------------------------------------------------------------------------

def _fallback_plan(slide: SlideSpec) -> OverlayPlan:
    region = OverlayRegion(
        name="bottom_band",
        x=_FALLBACK_X,
        y=_FALLBACK_Y,
        width=_FALLBACK_W,
        height=_FALLBACK_H,
    )
    style = OverlayStyle(
        text_color=_FALLBACK_COLOR,
        font_size=_FALLBACK_FONT_SIZE,
        use_backing=False,
        shadow=False,
    )
    return OverlayPlan(
        slide_index=slide.index,
        region=region,
        style=style,
        text=_extract_overlay_text(slide),
        diagnostics={"fallback": True, "reason": "analysis_skipped"},
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_overlay_plan(slide: SlideSpec, image_path: Path) -> OverlayPlan:
    """Return a deterministic OverlayPlan for a slide's image asset.

    Uses Pillow to analyse candidate regions. Falls back to a 012-compatible
    fixed plan if Pillow is unavailable or the image cannot be read.
    """
    preferred = _KIND_PREFERENCES.get(slide.kind, _DEFAULT_PREFERENCES)
    font_size = _FONT_OVERLAY_COVER if slide.kind == "cover" else _FONT_OVERLAY
    text = _extract_overlay_text(slide)

    try:
        # Sample all candidates and score
        scored: list[tuple[float, OverlayRegion, float, float]] = []
        for region in _CANDIDATE_REGIONS:
            mean_lum, stddev_lum = _sample_luminance(image_path, region)
            score = _score_region(region, mean_lum, stddev_lum, preferred)
            scored.append((score, region, mean_lum, stddev_lum))

        scored.sort(key=lambda t: t[0])
        best_score, best_region, best_mean, best_stddev = scored[0]

        color = _choose_color(best_mean)
        use_backing = _needs_backing(best_mean, best_stddev)

        style = OverlayStyle(
            text_color=color,
            font_size=font_size,
            use_backing=use_backing,
            backing_color="#000000" if use_backing else None,
            backing_opacity=0.45 if use_backing else None,
            shadow=False,
        )
        diagnostics: dict[str, float | str | bool] = {
            "fallback": False,
            "selected_region": best_region.name,
            "mean_luminance": round(best_mean, 2),
            "stddev_luminance": round(best_stddev, 2),
            "score": round(best_score, 2),
            "text_color": color,
            "use_backing": use_backing,
        }
        return OverlayPlan(
            slide_index=slide.index,
            region=best_region,
            style=style,
            text=text,
            diagnostics=diagnostics,
        )

    except Exception:
        plan = _fallback_plan(slide)
        plan.style.font_size = font_size
        plan.text = text
        return plan
