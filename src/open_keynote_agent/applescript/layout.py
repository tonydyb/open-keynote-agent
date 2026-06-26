from __future__ import annotations


def _parse_newline_list(text: str) -> list[str]:
    """Parse newline-delimited osascript output into a list of non-empty strings."""
    return [line for line in text.splitlines() if line.strip()]


LAYOUT_CANDIDATES: dict[str, list[str]] = {
    "title": ["Title", "Title Slide", "Title Only"],
    "title_body": ["Title & Bullets", "Title, Content", "Title and Bullets"],
    "blank": ["Blank"],
}


def resolve_layout_name(semantic: str, available: list[str]) -> str:
    """Return the AppleScript master slide name for a semantic layout key.

    Resolution order:
    1. Exact match — if semantic is itself an available layout name, return it.
    2. Semantic key — return the first LAYOUT_CANDIDATES entry present in available.
    3. Raise ValueError with the requested layout and the available choices.
    """
    if semantic in available:
        return semantic
    candidates = LAYOUT_CANDIDATES.get(semantic, [])
    for candidate in candidates:
        if candidate in available:
            return candidate
    raise ValueError(
        f"Cannot resolve layout {semantic!r}. "
        f"Available layouts: {available}. "
        f"Known candidates: {candidates}."
    )
