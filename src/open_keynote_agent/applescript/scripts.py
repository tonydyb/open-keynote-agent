from __future__ import annotations


def _n(value: float) -> str:
    """Format a number for AppleScript: emit as int when it is a whole number."""
    return str(int(value)) if isinstance(value, float) and value == int(value) else str(value)


def applescript_string(value: str) -> str:
    """Escape value for safe interpolation into an AppleScript double-quoted string literal."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def list_themes() -> str:
    """Return an AppleScript that outputs installed Keynote theme names, one per line."""
    return (
        'tell application "Keynote"\n'
        "    set oldDelimiters to AppleScript's text item delimiters\n"
        '    set AppleScript\'s text item delimiters to "\\n"\n'
        "    set output to (name of every theme) as text\n"
        "    set AppleScript's text item delimiters to oldDelimiters\n"
        "    return output\n"
        "end tell"
    )


def list_layouts() -> str:
    """Return an AppleScript that outputs slide layout names for the front document, one per line."""
    return (
        'tell application "Keynote"\n'
        "    set oldDelimiters to AppleScript's text item delimiters\n"
        '    set AppleScript\'s text item delimiters to "\\n"\n'
        "    set output to (name of every master slide of front document) as text\n"
        "    set AppleScript's text item delimiters to oldDelimiters\n"
        "    return output\n"
        "end tell"
    )


def create_document(name: str, theme: str | None = None) -> str:
    """Return an AppleScript that opens Keynote and creates a new front document.

    The document name is recorded in context["keynote"] by the handler, not here —
    Keynote's scripting dictionary exposes document name as read-only.
    The name argument is accepted for the escaping requirement but is not interpolated.

    If theme is provided, creates the document using that named theme.
    """
    applescript_string(name)  # validate escaping path; name is session-only
    if theme is not None:
        safe_theme = applescript_string(theme)
        return (
            'tell application "Keynote"\n'
            "    activate\n"
            f'    make new document with properties {{document theme:theme "{safe_theme}"}}\n'
            "end tell"
        )
    return (
        'tell application "Keynote"\n'
        "    activate\n"
        "    make new document\n"
        "end tell"
    )


def add_slide(master_name: str) -> str:
    """Return an AppleScript that adds a new slide at the end of the front document.

    master_name is the resolved AppleScript master name (e.g. "Title & Bullets").
    """
    safe_master = applescript_string(master_name)
    return (
        'tell application "Keynote"\n'
        "    tell front document\n"
        f'        make new slide at end of slides with properties {{base layout:master slide "{safe_master}"}}\n'
        "    end tell\n"
        "end tell"
    )


def set_slide_title(slide: int, title: str) -> str:
    """Return an AppleScript that sets the default title item text of slide N (1-indexed)."""
    safe_title = applescript_string(title)
    return (
        'tell application "Keynote"\n'
        "    tell front document\n"
        f"        tell slide {slide}\n"
        f'            set object text of default title item to "{safe_title}"\n'
        "        end tell\n"
        "    end tell\n"
        "end tell"
    )


def set_slide_body(slide: int, body: str) -> str:
    """Return an AppleScript that sets the default body item text of slide N (1-indexed)."""
    safe_body = applescript_string(body)
    return (
        'tell application "Keynote"\n'
        "    tell front document\n"
        f"        tell slide {slide}\n"
        f'            set object text of default body item to "{safe_body}"\n'
        "        end tell\n"
        "    end tell\n"
        "end tell"
    )


def export_pdf(posix_path: str) -> str:
    """Return an AppleScript that exports the front document to the given POSIX path as PDF."""
    safe_path = applescript_string(posix_path)
    return (
        'tell application "Keynote"\n'
        f'    export front document to POSIX file "{safe_path}" as PDF\n'
        "end tell"
    )


def add_text_box(
    slide: int,
    object_id: str,
    text: str,
    x: float,
    y: float,
    width: float,
    height: float,
    font_size: float | None = None,
    font_color: tuple[int, int, int] | None = None,
) -> str:
    """Return AppleScript that creates a text box and returns its text-item index."""
    applescript_string(object_id)  # object_id is tracked locally; Keynote has no writable object name
    safe_text = applescript_string(text)
    lines = [
        'tell application "Keynote"',
        "    tell front document",
        f"        tell slide {slide}",
        # Keynote rejects properties records on text item creation; create bare then set each property.
        "            set textItem to make new text item",
        f'            set object text of textItem to "{safe_text}"',
        f"            set position of textItem to {{{_n(x)}, {_n(y)}}}",
        f"            set width of textItem to {_n(width)}",
        f"            set height of textItem to {_n(height)}",
    ]
    if font_size is not None:
        lines.append(
            f"            set size of every paragraph of object text of textItem to {_n(font_size)}"
        )
    if font_color is not None:
        r, g, b = font_color
        lines.append(
            f"            set text color of every paragraph of object text of textItem to {{{r}, {g}, {b}}}"
        )
    lines += [
        "            return count of text items",
        "        end tell",
        "    end tell",
        "end tell",
    ]
    return "\n".join(lines)


def add_shape(
    slide: int,
    object_id: str,
    shape_type: str,
    x: float,
    y: float,
    width: float,
    height: float,
    fill_color: tuple[int, int, int] | None = None,
) -> str:
    """Return AppleScript that creates a default shape and returns its shape index.

    shape_type is retained for API clarity but Keynote does not expose a writable
    shape type property in its current AppleScript dictionary.
    """
    applescript_string(object_id)  # object_id is tracked locally; Keynote has no writable object name
    if fill_color is not None:
        raise ValueError("fill_color is not supported by Keynote AppleScript in this adapter yet")
    lines = [
        'tell application "Keynote"',
        "    tell front document",
        f"        tell slide {slide}",
        "            set shapeItem to make new shape",
        f"            set position of shapeItem to {{{_n(x)}, {_n(y)}}}",
        f"            set width of shapeItem to {_n(width)}",
        f"            set height of shapeItem to {_n(height)}",
    ]
    lines += [
        "            return count of shapes",
        "        end tell",
        "    end tell",
        "end tell",
    ]
    return "\n".join(lines)


def move_object(slide: int, apple_class: str, apple_index: int, x: float, y: float) -> str:
    """Return AppleScript that moves a tracked object on the given slide to (x, y)."""
    return (
        'tell application "Keynote"\n'
        "    tell front document\n"
        f"        tell slide {slide}\n"
        f"            set targetItem to {apple_class} {apple_index}\n"
        f"            set position of targetItem to {{{_n(x)}, {_n(y)}}}\n"
        "        end tell\n"
        "    end tell\n"
        "end tell"
    )


def resize_object(slide: int, apple_class: str, apple_index: int, width: float, height: float) -> str:
    """Return AppleScript that resizes a tracked object on the given slide."""
    return (
        'tell application "Keynote"\n'
        "    tell front document\n"
        f"        tell slide {slide}\n"
        f"            set targetItem to {apple_class} {apple_index}\n"
        f"            set width of targetItem to {_n(width)}\n"
        f"            set height of targetItem to {_n(height)}\n"
        "        end tell\n"
        "    end tell\n"
        "end tell"
    )


def get_document_info() -> str:
    """Return an AppleScript that outputs '<name>|<slide_count>' for the front document."""
    return (
        'tell application "Keynote"\n'
        "    set docName to name of front document\n"
        "    set slideCount to count of slides of front document\n"
        '    return docName & "|" & slideCount\n'
        "end tell"
    )
