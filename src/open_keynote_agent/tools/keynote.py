from __future__ import annotations

from pathlib import Path
from typing import Any

from open_keynote_agent.agent.registry import ToolDefinition, ToolRegistry
from open_keynote_agent.applescript import scripts
from open_keynote_agent.applescript.runner import ScriptRunner

_LAYOUT_MAP: dict[str, str] = {
    "title": "Title Slide",
    "title_body": "Title, Content",
    "blank": "Blank",
}


def _make_create_document(runner: ScriptRunner):
    def handler(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        name = args["name"]
        script = scripts.create_document(name)
        result = runner.run(script)
        if not result.ok:
            raise RuntimeError(result.stderr or "AppleScript error")
        context["keynote"] = {"name": name, "slide_count": 1}
        return {"observation": f'Created document "{name}".', "name": name}

    return handler


def _make_add_slide(runner: ScriptRunner):
    def handler(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        layout = args["layout"]
        master_name = _LAYOUT_MAP.get(layout)
        if master_name is None:
            valid = ", ".join(_LAYOUT_MAP)
            raise ValueError(f"Unknown layout {layout!r}. Valid values: {valid}.")
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
        name="keynote.create_document",
        description="Open Keynote and create a new front document with the given name.",
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Document name (session label only, not a saved file name)"}},
            "required": ["name"],
        },
        mutating=True,
        handler=_make_create_document(runner),
    ))
    registry.register(ToolDefinition(
        name="keynote.add_slide",
        description="Add a slide to the front Keynote document. layout must be one of: title, title_body, blank.",
        parameters={
            "type": "object",
            "properties": {
                "layout": {
                    "type": "string",
                    "description": "Slide layout. Allowed values: title, title_body, blank.",
                    "enum": ["title", "title_body", "blank"],
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
