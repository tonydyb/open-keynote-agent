from __future__ import annotations

from pathlib import Path
from typing import Any

from open_keynote_agent.agent.registry import ToolDefinition, ToolRegistry
from open_keynote_agent.applescript import scripts
from open_keynote_agent.applescript.layout import LAYOUT_CANDIDATES, _parse_newline_list, resolve_layout_name
from open_keynote_agent.applescript.runner import ScriptRunner


def _make_list_themes(runner: ScriptRunner):
    def handler(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        script = scripts.list_themes()
        result = runner.run(script)
        if not result.ok:
            raise RuntimeError(result.stderr or "AppleScript error")
        themes = _parse_newline_list(result.stdout)
        kn = context.setdefault("keynote", {})
        kn["themes"] = themes
        return {"observation": f"Found {len(themes)} theme(s).", "themes": themes}

    return handler


def _make_create_document(runner: ScriptRunner):
    def handler(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        name = args["name"]
        theme = args.get("theme")
        script = scripts.create_document(name, theme=theme)
        result = runner.run(script)
        if not result.ok:
            raise RuntimeError(result.stderr or "AppleScript error")
        # Preserve non-document-specific discovery data (e.g. themes) while
        # clearing stale document fields like layouts from a prior document.
        existing = context.get("keynote", {})
        kn: dict[str, Any] = {"name": name, "slide_count": 1}
        if "themes" in existing:
            kn["themes"] = existing["themes"]
        if theme is not None:
            kn["theme"] = theme
        context["keynote"] = kn
        obs = f'Created document "{name}".'
        if theme:
            obs = f'Created document "{name}" with theme "{theme}".'
        return {"observation": obs, "name": name}

    return handler


def _make_list_layouts(runner: ScriptRunner):
    def handler(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        script = scripts.list_layouts()
        result = runner.run(script)
        if not result.ok:
            raise RuntimeError(result.stderr or "AppleScript error")
        layouts = _parse_newline_list(result.stdout)
        kn = context.setdefault("keynote", {})
        kn["layouts"] = layouts
        return {"observation": f"Found {len(layouts)} layout(s).", "layouts": layouts}

    return handler


def _fetch_layouts(runner: ScriptRunner, context: dict[str, Any]) -> list[str]:
    """Return layouts from context if cached; otherwise fetch via list_layouts and cache."""
    kn = context.setdefault("keynote", {})
    if "layouts" in kn:
        return kn["layouts"]
    script = scripts.list_layouts()
    result = runner.run(script)
    if not result.ok:
        raise RuntimeError(result.stderr or "AppleScript error listing layouts")
    layouts = _parse_newline_list(result.stdout)
    kn["layouts"] = layouts
    return layouts


def _make_resolve_layout(runner: ScriptRunner):
    def handler(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        semantic = args["layout"]
        available = _fetch_layouts(runner, context)
        resolved = resolve_layout_name(semantic, available)
        return {
            "observation": f"Resolved layout {semantic!r} to {resolved!r}.",
            "layout": semantic,
            "resolved": resolved,
        }

    return handler


def _make_add_slide(runner: ScriptRunner):
    def handler(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        layout = args["layout"]
        # Validate that the semantic key is known before touching the runner
        if layout not in LAYOUT_CANDIDATES and not layout.startswith("_"):
            # Allow pass-through for exact layout names; reject obviously unknown semantics
            pass
        available = _fetch_layouts(runner, context)
        try:
            master_name = resolve_layout_name(layout, available)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        script = scripts.add_slide(master_name)
        result = runner.run(script)
        if not result.ok:
            raise RuntimeError(result.stderr or "AppleScript error")
        kn = context.setdefault("keynote", {"name": "", "slide_count": 0})
        kn["slide_count"] = kn.get("slide_count", 0) + 1
        return {
            "observation": f"Added slide with layout '{layout}'.",
            "layout": layout,
            "slide_count": kn["slide_count"],
        }

    return handler


def _make_set_slide_title(runner: ScriptRunner):
    def handler(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        slide = args["slide"]
        title = args["title"]
        if slide < 1:
            raise ValueError(f"Slide index must be >= 1, got {slide}.")
        script = scripts.set_slide_title(slide, title)
        result = runner.run(script)
        if not result.ok:
            raise RuntimeError(result.stderr or "AppleScript error")
        return {"observation": f"Set title of slide {slide}.", "slide": slide, "title": title}

    return handler


def _make_set_slide_body(runner: ScriptRunner):
    def handler(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        slide = args["slide"]
        body = args["body"]
        if slide < 1:
            raise ValueError(f"Slide index must be >= 1, got {slide}.")
        script = scripts.set_slide_body(slide, body)
        result = runner.run(script)
        if not result.ok:
            raise RuntimeError(result.stderr or "AppleScript error")
        return {"observation": f"Set body of slide {slide}.", "slide": slide, "body": body}

    return handler


def _make_export_pdf(runner: ScriptRunner):
    def handler(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        raw_path = args["path"]
        resolved = Path(raw_path).expanduser().resolve()
        if not resolved.parent.exists():
            raise RuntimeError(f"Export parent directory does not exist: {resolved.parent}")
        if resolved.exists():
            raise RuntimeError(f"Export path already exists: {resolved}")
        script = scripts.export_pdf(str(resolved))
        result = runner.run(script)
        if not result.ok:
            raise RuntimeError(result.stderr or "AppleScript error")
        return {"observation": f"Exported PDF to {resolved}.", "path": str(resolved)}

    return handler


def _make_get_document_info(runner: ScriptRunner):
    def handler(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        script = scripts.get_document_info()
        result = runner.run(script)
        if not result.ok:
            raise RuntimeError(result.stderr or "AppleScript error")
        raw = result.stdout.strip()
        try:
            name, count_str = raw.split("|", 1)
            slide_count = int(count_str.strip())
        except (ValueError, AttributeError):
            raise RuntimeError(f"Unexpected get_document_info output: {raw!r}")
        kn = context.setdefault("keynote", {})
        kn["name"] = name.strip()
        kn["slide_count"] = slide_count
        return {
            "observation": f'Document "{name.strip()}" has {slide_count} slide(s).',
            "name": name.strip(),
            "slide_count": slide_count,
        }

    return handler


def register_keynote_tools(registry: ToolRegistry, runner: ScriptRunner) -> None:
    registry.register(ToolDefinition(
        name="keynote.list_themes",
        description="Return a list of installed Keynote theme names.",
        parameters={"type": "object", "properties": {}},
        mutating=False,
        handler=_make_list_themes(runner),
    ))
    registry.register(ToolDefinition(
        name="keynote.create_document",
        description="Open Keynote and create a new front document. Optionally specify a theme.",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Document name (session label only, not a saved file name)"},
                "theme": {"type": "string", "description": "Optional Keynote theme name (e.g. 'Parchment', 'Basic White')"},
            },
            "required": ["name"],
        },
        mutating=True,
        handler=_make_create_document(runner),
    ))
    registry.register(ToolDefinition(
        name="keynote.list_layouts",
        description="Return a list of slide layout names for the front Keynote document.",
        parameters={"type": "object", "properties": {}},
        mutating=False,
        handler=_make_list_layouts(runner),
    ))
    registry.register(ToolDefinition(
        name="keynote.resolve_layout",
        description="Resolve a semantic layout name (e.g. 'title_body') to the actual Keynote layout name.",
        parameters={
            "type": "object",
            "properties": {
                "layout": {"type": "string", "description": "Semantic layout name: title, title_body, or blank"},
            },
            "required": ["layout"],
        },
        mutating=False,
        handler=_make_resolve_layout(runner),
    ))
    registry.register(ToolDefinition(
        name="keynote.add_slide",
        description="Add a slide to the front Keynote document using a semantic layout name.",
        parameters={
            "type": "object",
            "properties": {
                "layout": {
                    "type": "string",
                    "description": "Semantic layout name (title, title_body, or blank).",
                }
            },
            "required": ["layout"],
        },
        mutating=True,
        handler=_make_add_slide(runner),
    ))
    registry.register(ToolDefinition(
        name="keynote.set_slide_title",
        description="Set the title text of a slide (1-indexed) in the front Keynote document.",
        parameters={
            "type": "object",
            "properties": {
                "slide": {"type": "integer", "description": "Slide number (1-indexed)"},
                "title": {"type": "string", "description": "Title text"},
            },
            "required": ["slide", "title"],
        },
        mutating=True,
        handler=_make_set_slide_title(runner),
    ))
    registry.register(ToolDefinition(
        name="keynote.set_slide_body",
        description="Set the body text of a slide (1-indexed) in the front Keynote document.",
        parameters={
            "type": "object",
            "properties": {
                "slide": {"type": "integer", "description": "Slide number (1-indexed)"},
                "body": {"type": "string", "description": "Body text"},
            },
            "required": ["slide", "body"],
        },
        mutating=True,
        handler=_make_set_slide_body(runner),
    ))
    registry.register(ToolDefinition(
        name="keynote.export_pdf",
        description="Export the front Keynote document to a PDF at the given path. Parent directory must exist. Path must not already exist.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Output file path (POSIX path, parent must exist, must not already exist)"}},
            "required": ["path"],
        },
        mutating=True,
        handler=_make_export_pdf(runner),
    ))
    registry.register(ToolDefinition(
        name="keynote.get_document_info",
        description="Return the name and slide count of the front Keynote document.",
        parameters={"type": "object", "properties": {}},
        mutating=False,
        handler=_make_get_document_info(runner),
    ))
