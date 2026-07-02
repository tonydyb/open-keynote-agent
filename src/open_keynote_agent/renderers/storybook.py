from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from open_keynote_agent.agent.executor import execute_plan
from open_keynote_agent.agent.registry import ToolRegistry
from open_keynote_agent.agent.session import Plan, ProposedToolCall, SessionState
from open_keynote_agent.deck.schema import DeckSpec
from open_keynote_agent.renderers.templates import (
    LAYOUT_FOR_KIND,
    calls_for_slide,
    calls_for_slide_image_overlay,
    image_call_for_slide,
)

_THEME_FALLBACKS = ["Parchment", "Basic White"]


class RenderResult(BaseModel):
    deck_title: str
    theme: str
    slide_count: int
    pdf_path: str | None
    output_dir: str
    tool_results: list[dict[str, Any]]
    image_count: int = 0
    missing_image_slides: list[int] = Field(default_factory=list)


def _run_one(
    tool: str,
    args: dict[str, Any],
    description: str,
    registry: ToolRegistry,
    state: SessionState,
    tool_results: list[dict[str, Any]],
) -> None:
    """Run a single tool call and record the result. Raises RuntimeError on failure."""
    plan = Plan(steps=[ProposedToolCall(tool=tool, args=args, description=description)])
    results = execute_plan(plan, registry, state)
    for r in results:
        tool_results.append(r.model_dump())
    if not results or not results[-1].ok:
        err = results[-1].error if results else "no result"
        raise RuntimeError(f"{tool} failed: {err}")


def render_storybook_deck(
    deck: DeckSpec,
    registry: ToolRegistry,
    state: SessionState,
    *,
    output_dir: Path,
    export_pdf: bool = True,
    image_assets: dict[int, Path] | None = None,
) -> RenderResult:
    if deck.slides[0].kind != "cover":
        raise ValueError(
            f"First slide must be kind 'cover', got {deck.slides[0].kind!r}. "
            "Storybook renderer requires a cover slide as the first slide."
        )

    tool_results: list[dict[str, Any]] = []
    image_count = 0
    missing_image_slides: list[int] = []

    # 1. List themes and select one
    _run_one("keynote.list_themes", {}, "List Keynote themes", registry, state, tool_results)
    available_themes: list[str] = state.context.get("keynote", {}).get("themes", [])

    selected_theme: str
    if deck.theme and deck.theme in available_themes:
        selected_theme = deck.theme
    else:
        for candidate in _THEME_FALLBACKS:
            if candidate in available_themes:
                selected_theme = candidate
                break
        else:
            selected_theme = available_themes[0] if available_themes else "Parchment"

    # 2. Create document
    _run_one(
        "keynote.create_document",
        {"name": deck.title, "theme": selected_theme},
        f"Create document '{deck.title}'",
        registry, state, tool_results,
    )

    # 3. List layouts
    _run_one("keynote.list_layouts", {}, "List layouts", registry, state, tool_results)

    # 4. Render slides.
    # Slide 1 is the default slide Keynote creates — do NOT call add_slide for it.
    # Call add_slide for slides 2..N.
    for slide_spec in deck.slides:
        keynote_slide_num = slide_spec.index  # 1-indexed, matches SlideSpec.index
        has_image = image_assets is not None and slide_spec.index in image_assets

        if slide_spec.index > 1:
            layout = "blank" if has_image else LAYOUT_FOR_KIND.get(slide_spec.kind, "title_body")
            _run_one(
                "keynote.add_slide",
                {"layout": layout},
                f"Add slide {slide_spec.index} ({slide_spec.kind})",
                registry, state, tool_results,
            )

        # Keep the cover title. For image-backed pages after the cover, avoid
        # presentation-style default titles and render text as image overlay.
        if slide_spec.index == 1 or not has_image:
            _run_one(
                "keynote.set_slide_title",
                {"slide": keynote_slide_num, "title": slide_spec.title},
                f"Set title of slide {keynote_slide_num}",
                registry, state, tool_results,
            )

        # Image asset or emoji/shape fallback
        if has_image:
            image_path = image_assets[slide_spec.index]
            img_call = image_call_for_slide(slide_spec, image_path)
            _run_one(
                img_call.tool,
                img_call.args,
                img_call.description,
                registry, state, tool_results,
            )
            image_count += 1
            object_calls = calls_for_slide_image_overlay(slide_spec, image_path)
        else:
            if image_assets is not None:
                missing_image_slides.append(slide_spec.index)
            object_calls = calls_for_slide(slide_spec)

        if object_calls:
            plan = Plan(steps=object_calls)
            results = execute_plan(plan, registry, state)
            for r in results:
                tool_results.append(r.model_dump())
            failed = [r for r in results if not r.ok]
            if failed:
                raise RuntimeError(
                    f"Slide {keynote_slide_num} object call failed: {failed[0].error}"
                )

    # 5. Export PDF
    pdf_path: str | None = None
    if export_pdf:
        pdf_file = output_dir / f"{deck.title}.pdf"
        _run_one(
            "keynote.export_pdf",
            {"path": str(pdf_file)},
            "Export PDF",
            registry, state, tool_results,
        )
        pdf_path = str(pdf_file)

    return RenderResult(
        deck_title=deck.title,
        theme=selected_theme,
        slide_count=len(deck.slides),
        pdf_path=pdf_path,
        output_dir=str(output_dir),
        tool_results=tool_results,
        image_count=image_count,
        missing_image_slides=missing_image_slides,
    )
