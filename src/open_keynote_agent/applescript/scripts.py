from __future__ import annotations


def applescript_string(value: str) -> str:
    """Escape value for safe interpolation into an AppleScript double-quoted string literal."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def create_document(name: str) -> str:
    """Return an AppleScript that opens Keynote and creates a new front document.

    The document name is recorded in context["keynote"] by the handler, not here —
    Keynote's scripting dictionary exposes document name as read-only.
    The name argument is accepted for the escaping requirement but is not interpolated.
    """
    applescript_string(name)  # validate escaping path; name is session-only
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


def get_document_info() -> str:
    """Return an AppleScript that outputs '<name>|<slide_count>' for the front document."""
    return (
        'tell application "Keynote"\n'
        "    set docName to name of front document\n"
        "    set slideCount to count of slides of front document\n"
        '    return docName & "|" & slideCount\n'
        "end tell"
    )
