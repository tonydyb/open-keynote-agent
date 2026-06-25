from __future__ import annotations

from pathlib import Path
from typing import Any

from open_keynote_agent.agent.registry import ToolDefinition, ToolRegistry


def _get_doc(context: dict[str, Any]) -> dict[str, Any]:
    doc = context.get("demo")
    if not doc:
        raise ValueError("No document created yet. Run demo.create_document first.")
    return doc


def _create_document(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    context["demo"] = {"name": name, "slides": []}
    return {"observation": f'Created document "{name}" with 0 slides.', "name": name, "slides": []}


def _add_slide(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    doc = _get_doc(context)
    kind = args["kind"]
    title = args["title"]
    slide = {"kind": kind, "title": title, "text": ""}
    doc["slides"].append(slide)
    index = len(doc["slides"])
    return {
        "observation": f'Added slide {index}: {kind} "{title}".',
        "slide_index": index,
        "slide": slide,
    }


def _set_text(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    doc = _get_doc(context)
    slide_num = args["slide"]
    text = args["text"]
    slides = doc["slides"]
    if slide_num < 1 or slide_num > len(slides):
        raise ValueError(f"Slide {slide_num} does not exist (document has {len(slides)} slides).")
    slides[slide_num - 1]["text"] = text
    return {
        "observation": f"Set text on slide {slide_num}.",
        "slide_index": slide_num,
        "text": text,
    }


def _export_pdf(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    doc = _get_doc(context)
    name = doc["name"]
    out_path = Path(args.get("path") or f"{name}.pdf")
    out_path.write_bytes(b"%PDF-1.4 placeholder\n")
    context["demo"]["pdf_path"] = str(out_path)
    return {"observation": f"Exported to {out_path}.", "path": str(out_path)}


def _get_document_info(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    doc = context.get("demo")
    if not doc:
        return {"observation": "No document created yet.", "name": None, "slide_count": 0}
    return {
        "observation": f'Document "{doc["name"]}" has {len(doc["slides"])} slide(s).',
        "name": doc["name"],
        "slide_count": len(doc["slides"]),
    }


def register_demo_tools(registry: ToolRegistry) -> None:
    registry.register(ToolDefinition(
        name="demo.create_document",
        description="Create a new demo Keynote document with the given name.",
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Document name"}},
            "required": ["name"],
        },
        mutating=True,
        handler=_create_document,
    ))
    registry.register(ToolDefinition(
        name="demo.add_slide",
        description="Add a slide to the current demo document.",
        parameters={
            "type": "object",
            "properties": {
                "kind": {"type": "string", "description": "Slide kind, e.g. 'title' or 'body'"},
                "title": {"type": "string", "description": "Slide title text"},
            },
            "required": ["kind", "title"],
        },
        mutating=True,
        handler=_add_slide,
    ))
    registry.register(ToolDefinition(
        name="demo.set_text",
        description="Set the body text of a slide (1-indexed).",
        parameters={
            "type": "object",
            "properties": {
                "slide": {"type": "integer", "description": "Slide number (1-indexed)"},
                "text": {"type": "string", "description": "Text content"},
            },
            "required": ["slide", "text"],
        },
        mutating=True,
        handler=_set_text,
    ))
    registry.register(ToolDefinition(
        name="demo.export_pdf",
        description="Export the current demo document to a PDF file.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Output path (optional, defaults to <name>.pdf)"},
            },
        },
        mutating=True,
        handler=_export_pdf,
    ))
    registry.register(ToolDefinition(
        name="demo.get_document_info",
        description="Return the current document name and slide count.",
        parameters={"type": "object", "properties": {}},
        mutating=False,
        handler=_get_document_info,
    ))
