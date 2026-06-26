# Tasks

## 1. AppleScript Builders

- [x] Add `scripts.list_themes()` using `AppleScript's text item delimiters` so `osascript` returns newline-delimited installed Keynote theme names.
- [x] Add `scripts.list_layouts()` using `AppleScript's text item delimiters` so `osascript` returns newline-delimited slide layouts for the front document.
- [x] Extend `scripts.create_document(name, theme=None)` to support `document theme:theme "<theme>"`.
- [x] Keep the `name` argument session-only; do not include it in AppleScript document properties.
- [x] Ensure all theme/layout string interpolation uses `applescript_string`.
- [x] Add unit tests for the new builders and escaping behavior.

## 2. Parsing Helpers

- [x] Add `src/open_keynote_agent/applescript/layout.py`.
- [x] Add `_parse_newline_list(text: str) -> list[str]` to `applescript/layout.py`.
- [x] Do not parse AppleScript list output by splitting on commas.
- [x] Add `LAYOUT_CANDIDATES` for `title`, `title_body`, and `blank` in `applescript/layout.py`.
- [x] Add `resolve_layout_name(semantic, available)` helper in `applescript/layout.py`.
- [x] Remove `_LAYOUT_MAP` from `src/open_keynote_agent/tools/keynote.py`.
- [x] Add unit tests for exact layout matches.
- [x] Add unit tests for semantic layout resolution.
- [x] Add unit tests for unknown layout errors.

## 3. Keynote Tools

- [x] Add `keynote.list_themes` tool.
- [x] Add optional `theme` parameter to `keynote.create_document`.
- [x] Add `keynote.list_layouts` tool.
- [x] Add `keynote.resolve_layout` tool.
- [x] Ensure `keynote.resolve_layout` calls `list_layouts` and updates context when layouts are absent.
- [x] Update `keynote.add_slide` to resolve layouts against discovered front-document layouts.
- [x] Ensure `keynote.add_slide` does not call `list_layouts` when `context["keynote"]["layouts"]` is already present.
- [x] Ensure `keynote.add_slide` calls `list_layouts` and updates context when layouts are absent.
- [x] Update context with discovered themes, layouts, selected theme, and resolved layouts where useful.
- [x] Treat `slide_count: 1` after theme-based document creation as best-effort; keep `keynote.get_document_info` authoritative for actual slide count.

## 4. Tests

- [x] Add unit tests for `keynote.list_themes` with `FakeScriptRunner`.
- [x] Add unit tests for `keynote.create_document` with and without `theme`.
- [x] Add unit tests for `keynote.list_layouts` with `FakeScriptRunner`.
- [x] Add unit tests for `keynote.resolve_layout` using cached layouts.
- [x] Add unit tests for `keynote.resolve_layout` fetching layouts when missing.
- [x] Add unit tests for `keynote.add_slide` resolving `title_body` to `Title & Bullets`.
- [x] Update existing `TestAddSlide` tests to pre-populate `context["keynote"]["layouts"]` or configure a fake `list_layouts` response.
- [x] Add tests proving comma-containing layout names are preserved when parsing newline-delimited output.
- [x] Add unit tests verifying no real `osascript` call is required.

## 5. Integration Smoke Test

- [x] Update skipped-by-default Keynote integration smoke test to list themes.
- [x] Select `Parchment` if present in the returned theme list.
- [x] Otherwise select `Basic White` if present.
- [x] Otherwise select the first returned theme.
- [x] Create document with selected theme.
- [x] List layouts.
- [x] Add a `title_body` slide through semantic resolution.
- [x] Export PDF.

## 6. Documentation

- [x] Update README with `keynote.list_themes`, `keynote.list_layouts`, and `theme` usage examples.
- [x] Document `Parchment` as the preferred built-in storybook theme.
- [ ] Update CLAUDE.md and AGENTS.md with the theme/layout discovery workflow.

## 7. Quality Bar

- [x] Run `uv run pytest`.
- [x] Run `uv run ruff check .`.
- [x] Run `uv run oka session --tools keynote --help`.
- [x] Confirm non-integration tests do not require Keynote or macOS Automation permissions.
