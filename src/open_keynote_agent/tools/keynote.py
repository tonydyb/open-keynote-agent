from __future__ import annotations

from pathlib import Path
from typing import Any

from open_keynote_agent.agent.registry import ToolDefinition, ToolRegistry
from open_keynote_agent.applescript import scripts
from open_keynote_agent.applescript.layout import LAYOUT_CANDIDATES, _parse_newline_list, resolve_layout_name
from open_keynote_agent.applescript.objects import (
    SHAPE_MAP,
    commit_object_id,
    generate_object_id,
    hex_to_rgb_tuple,
    validate_geometry,
    validate_object_id,
)
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


def _resolve_object_id(
    args: dict[str, Any], slide: int, kind: str, context: dict[str, Any]
) -> tuple[str, bool]:
    """Return (object_id, auto_generated) without committing any counter.

    The counter is committed by calling commit_object_id() after runner success.
    """
    if "object_id" in args:
        oid = args["object_id"]
        validate_object_id(oid)
        auto = False
    else:
        oid = generate_object_id(slide, kind, context)
        auto = True
    existing = context.get("keynote", {}).get("objects", {})
    if oid in existing:
        raise ValueError(f"Duplicate object_id {oid!r}. Already registered in this session.")
    return oid, auto


def _register_object(context: dict[str, Any], entry: dict[str, Any]) -> None:
    """Write object entry into context["keynote"]["objects"] and ["slides"] index."""
    kn = context.setdefault("keynote", {})
    kn.setdefault("objects", {})[entry["object_id"]] = entry
    slide_key = str(entry["slide"])
    kn.setdefault("slides", {}).setdefault(slide_key, {"objects": []})["objects"].append(
        entry["object_id"]
    )


def _parse_created_index(stdout: str, kind: str) -> int:
    raw = stdout.strip()
    try:
        value = int(raw)
    except ValueError:
        raise RuntimeError(f"Unexpected {kind} creation output: {raw!r}")
    if value < 1:
        raise RuntimeError(f"Unexpected {kind} creation index: {value}")
    return value


def _make_add_text_box(runner: ScriptRunner):
    def handler(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        slide = args["slide"]
        text = args["text"]
        x = float(args["x"])
        y = float(args["y"])
        width = float(args["width"])
        height = float(args["height"])
        font_size = args.get("font_size")
        font_color_hex = args.get("font_color")

        kn_slide_count = context.get("keynote", {}).get("slide_count")
        validate_geometry(slide, x, y, width, height, slide_count=kn_slide_count)

        font_color_rgb: tuple[int, int, int] | None = None
        if font_color_hex is not None:
            font_color_rgb = hex_to_rgb_tuple(font_color_hex)

        oid, auto = _resolve_object_id(args, slide, "text_box", context)

        script = scripts.add_text_box(
            slide=slide,
            object_id=oid,
            text=text,
            x=x,
            y=y,
            width=width,
            height=height,
            font_size=font_size,
            font_color=font_color_rgb,
        )
        result = runner.run(script)
        if not result.ok:
            raise RuntimeError(result.stderr or "AppleScript error")
        apple_index = _parse_created_index(result.stdout, "text item")

        if auto:
            commit_object_id(slide, "text_box", context)
        entry: dict[str, Any] = {
            "object_id": oid,
            "slide": slide,
            "type": "text_box",
            "apple_class": "text item",
            "apple_index": apple_index,
            "text": text,
            "x": x,
            "y": y,
            "width": width,
            "height": height,
        }
        _register_object(context, entry)
        return {"observation": f"Added text box {oid!r} on slide {slide}.", "object_id": oid}

    return handler


def _make_add_emoji_text(runner: ScriptRunner):
    def handler(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        slide = args["slide"]
        emoji = args["emoji"]
        x = float(args["x"])
        y = float(args["y"])
        size = float(args["size"])

        if size <= 0:
            raise ValueError(f"size must be > 0, got {size}.")

        kn_slide_count = context.get("keynote", {}).get("slide_count")
        if slide < 1:
            raise ValueError(f"slide must be >= 1, got {slide}.")
        if kn_slide_count is not None and slide > kn_slide_count:
            raise ValueError(f"slide {slide} exceeds known slide_count {kn_slide_count}.")
        if x < 0:
            raise ValueError(f"x must be >= 0, got {x}.")
        if y < 0:
            raise ValueError(f"y must be >= 0, got {y}.")

        width = size * 1.5
        height = size * 1.5
        font_size = size

        oid, auto = _resolve_object_id(args, slide, "emoji", context)

        script = scripts.add_text_box(
            slide=slide,
            object_id=oid,
            text=emoji,
            x=x,
            y=y,
            width=width,
            height=height,
            font_size=font_size,
            font_color=None,
        )
        result = runner.run(script)
        if not result.ok:
            raise RuntimeError(result.stderr or "AppleScript error")
        apple_index = _parse_created_index(result.stdout, "text item")

        if auto:
            commit_object_id(slide, "emoji", context)
        entry: dict[str, Any] = {
            "object_id": oid,
            "slide": slide,
            "type": "emoji",
            "apple_class": "text item",
            "apple_index": apple_index,
            "text": emoji,
            "x": x,
            "y": y,
            "width": width,
            "height": height,
        }
        _register_object(context, entry)
        return {"observation": f"Added emoji text {oid!r} on slide {slide}.", "object_id": oid}

    return handler


def _make_add_shape(runner: ScriptRunner):
    def handler(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        slide = args["slide"]
        shape = args["shape"]
        x = float(args["x"])
        y = float(args["y"])
        width = float(args["width"])
        height = float(args["height"])
        fill_color_hex = args.get("fill_color")

        if shape not in SHAPE_MAP:
            valid = ", ".join(SHAPE_MAP)
            raise ValueError(f"Unknown shape {shape!r}. Valid values: {valid}.")
        if fill_color_hex is not None:
            raise ValueError("fill_color is not supported by Keynote AppleScript in this adapter yet.")

        kn_slide_count = context.get("keynote", {}).get("slide_count")
        validate_geometry(slide, x, y, width, height, slide_count=kn_slide_count)

        oid, auto = _resolve_object_id(args, slide, "shape", context)
        shape_type = SHAPE_MAP[shape]

        script = scripts.add_shape(
            slide=slide,
            object_id=oid,
            shape_type=shape_type,
            x=x,
            y=y,
            width=width,
            height=height,
            fill_color=None,
        )
        result = runner.run(script)
        if not result.ok:
            raise RuntimeError(result.stderr or "AppleScript error")
        apple_index = _parse_created_index(result.stdout, "shape")

        if auto:
            commit_object_id(slide, "shape", context)
        entry: dict[str, Any] = {
            "object_id": oid,
            "slide": slide,
            "type": "shape",
            "apple_class": "shape",
            "apple_index": apple_index,
            "shape": shape,
            "x": x,
            "y": y,
            "width": width,
            "height": height,
        }
        _register_object(context, entry)
        return {"observation": f"Added {shape} shape {oid!r} on slide {slide}.", "object_id": oid}

    return handler


def _make_move_object(runner: ScriptRunner):
    def handler(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        oid = args["object_id"]
        x = float(args["x"])
        y = float(args["y"])

        objects = context.get("keynote", {}).get("objects", {})
        if oid not in objects:
            raise ValueError(f"Unknown object_id {oid!r}. Not found in session context.")

        if x < 0:
            raise ValueError(f"x must be >= 0, got {x}.")
        if y < 0:
            raise ValueError(f"y must be >= 0, got {y}.")

        obj = objects[oid]
        slide = obj["slide"]
        apple_class = obj["apple_class"]
        apple_index = obj["apple_index"]

        script = scripts.move_object(slide=slide, apple_class=apple_class, apple_index=apple_index, x=x, y=y)
        result = runner.run(script)
        if not result.ok:
            raise RuntimeError(result.stderr or "AppleScript error")
        # Update context only after confirmed script success
        obj["x"] = x
        obj["y"] = y
        return {"observation": f"Moved {oid!r} to ({x}, {y}).", "object_id": oid, "x": x, "y": y}

    return handler


def _make_resize_object(runner: ScriptRunner):
    def handler(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        oid = args["object_id"]
        width = float(args["width"])
        height = float(args["height"])

        objects = context.get("keynote", {}).get("objects", {})
        if oid not in objects:
            raise ValueError(f"Unknown object_id {oid!r}. Not found in session context.")

        if width <= 0:
            raise ValueError(f"width must be > 0, got {width}.")
        if height <= 0:
            raise ValueError(f"height must be > 0, got {height}.")

        obj = objects[oid]
        slide = obj["slide"]
        apple_class = obj["apple_class"]
        apple_index = obj["apple_index"]

        script = scripts.resize_object(slide=slide, apple_class=apple_class, apple_index=apple_index, width=width, height=height)
        result = runner.run(script)
        if not result.ok:
            raise RuntimeError(result.stderr or "AppleScript error")

        obj["width"] = width
        obj["height"] = height
        return {
            "observation": f"Resized {oid!r} to {width}x{height}.",
            "object_id": oid,
            "width": width,
            "height": height,
        }

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
    registry.register(ToolDefinition(
        name="keynote.add_text_box",
        description="Add a text box to a slide. Positions and sizes are in Keynote points (top-left origin).",
        parameters={
            "type": "object",
            "properties": {
                "slide": {"type": "integer", "description": "Slide number (1-indexed)"},
                "text": {"type": "string", "description": "Text content"},
                "x": {"type": "number", "description": "Left position in points"},
                "y": {"type": "number", "description": "Top position in points"},
                "width": {"type": "number", "description": "Width in points"},
                "height": {"type": "number", "description": "Height in points"},
                "object_id": {"type": "string", "description": "Optional stable object ID (auto-generated if omitted)"},
                "font_size": {"type": "number", "description": "Optional font size in points"},
                "font_color": {"type": "string", "description": "Optional hex font color e.g. #6B3F1D"},
            },
            "required": ["slide", "text", "x", "y", "width", "height"],
        },
        mutating=True,
        handler=_make_add_text_box(runner),
    ))
    registry.register(ToolDefinition(
        name="keynote.add_emoji_text",
        description="Add a large emoji as a text object on a slide.",
        parameters={
            "type": "object",
            "properties": {
                "slide": {"type": "integer", "description": "Slide number (1-indexed)"},
                "emoji": {"type": "string", "description": "Emoji character(s) to display"},
                "x": {"type": "number", "description": "Left position in points"},
                "y": {"type": "number", "description": "Top position in points"},
                "size": {"type": "number", "description": "Emoji font size in points (width and height are derived as size * 1.5)"},
                "object_id": {"type": "string", "description": "Optional stable object ID (auto-generated if omitted)"},
            },
            "required": ["slide", "emoji", "x", "y", "size"],
        },
        mutating=True,
        handler=_make_add_emoji_text(runner),
    ))
    registry.register(ToolDefinition(
        name="keynote.add_shape",
        description="Add a simple decorative shape to a slide.",
        parameters={
            "type": "object",
            "properties": {
                "slide": {"type": "integer", "description": "Slide number (1-indexed)"},
                "shape": {"type": "string", "description": "Shape type: rectangle"},
                "x": {"type": "number", "description": "Left position in points"},
                "y": {"type": "number", "description": "Top position in points"},
                "width": {"type": "number", "description": "Width in points"},
                "height": {"type": "number", "description": "Height in points"},
                "object_id": {"type": "string", "description": "Optional stable object ID (auto-generated if omitted)"},
                "fill_color": {"type": "string", "description": "Reserved for future support; currently rejected if provided"},
            },
            "required": ["slide", "shape", "x", "y", "width", "height"],
        },
        mutating=True,
        handler=_make_add_shape(runner),
    ))
    registry.register(ToolDefinition(
        name="keynote.move_object",
        description="Move a previously created object by its object_id to a new position.",
        parameters={
            "type": "object",
            "properties": {
                "object_id": {"type": "string", "description": "Object ID as recorded in session context"},
                "x": {"type": "number", "description": "New left position in points"},
                "y": {"type": "number", "description": "New top position in points"},
            },
            "required": ["object_id", "x", "y"],
        },
        mutating=True,
        handler=_make_move_object(runner),
    ))
    registry.register(ToolDefinition(
        name="keynote.resize_object",
        description="Resize a previously created object by its object_id.",
        parameters={
            "type": "object",
            "properties": {
                "object_id": {"type": "string", "description": "Object ID as recorded in session context"},
                "width": {"type": "number", "description": "New width in points"},
                "height": {"type": "number", "description": "New height in points"},
            },
            "required": ["object_id", "width", "height"],
        },
        mutating=True,
        handler=_make_resize_object(runner),
    ))
