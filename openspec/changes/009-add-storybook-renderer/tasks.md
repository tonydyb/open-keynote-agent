# Tasks

## 1. Renderer Package

- [x] Add `src/open_keynote_agent/renderers/__init__.py`.
- [x] Add `src/open_keynote_agent/renderers/templates.py`.
- [x] Add `src/open_keynote_agent/renderers/storybook.py`.
- [x] Define `RenderResult`.
- [x] Add `RenderResult.deck_title: str`.
- [x] Add `RenderResult.theme: str`.
- [x] Add `RenderResult.slide_count: int`.
- [x] Add `RenderResult.pdf_path: str | None`.
- [x] Add `RenderResult.output_dir: str`.
- [x] Add `RenderResult.tool_results: list[dict]`.
- [x] Ensure renderer imports DeckSpec but does not import any LLM provider.

## 2. Template System

- [x] Define shared 16:9 coordinate constants.
- [x] Define semantic layout mapping by `SlideSpec.kind`.
- [x] Implement cover template.
- [x] Implement characters template.
- [x] Implement chapter template.
- [x] Implement climax template.
- [x] Implement lesson template.
- [x] Implement ending template.
- [x] Implement content fallback template.
- [x] Alternate chapter visual placement by slide index.
- [x] Generate deterministic object IDs.
- [x] Add fallback emoji by slide kind.
- [x] Ensure templates emit only supported 007 shape calls: `shape="rectangle"` with no `fill_color`.

## 3. Renderer Execution

- [x] Implement `render_storybook_deck(deck, registry, state, output_dir, export_pdf=True)`.
- [x] Call `keynote.list_themes`.
- [x] Select theme using deck theme > Parchment > Basic White > first returned theme.
- [x] Call `keynote.create_document` with selected theme.
- [x] Call `keynote.list_layouts`.
- [x] Reject DeckSpecs whose first slide kind is not `cover` before mutating Keynote.
- [x] Use Keynote's default first slide for `DeckSpec.slides[0]`.
- [x] Call `keynote.add_slide` only for `DeckSpec.slides[1:]`.
- [x] Set slide title.
- [x] Execute template object calls.
- [x] Collect serialized tool results from every `execute_plan` call.
- [x] Export PDF when `export_pdf=True`.
- [x] Stop and fail clearly on failed tool result.
- [x] Return `RenderResult`.

## 4. CLI

- [x] Add `oka render-storybook <deck_spec.json>`.
- [x] Add `--output` option.
- [x] Add `--no-pdf` option.
- [x] Validate input path exists and is a file.
- [x] Read and validate `DeckSpec`.
- [x] Use unique default output directory under `.runs/<YYYYMMDDTHHMMSSZ>-storybook/`.
- [x] Refuse to overwrite existing `render_result.json`, `tool_results.jsonl`, or exported PDF.
- [x] Register Keynote tools with `OsascriptRunner`.
- [x] Print macOS Automation permission warning.
- [x] Write `render_result.json`.
- [x] Write `tool_results.jsonl` from `RenderResult.tool_results`.
- [x] Print output directory and PDF path.

## 5. Unit Tests

- [x] Add renderer/template tests.
- [x] Test theme fallback selection.
- [x] Test semantic layout mapping.
- [x] Test default Keynote slide 1 is reused for `DeckSpec.slides[0]`.
- [x] Test `keynote.add_slide` is called only for slides 2..N.
- [x] Test DeckSpecs whose first slide is not `cover` are rejected before mutation.
- [x] Test deterministic object IDs.
- [x] Test fallback emoji for empty visuals.
- [x] Test templates never emit unsupported shape kinds.
- [x] Test templates never pass `fill_color` to `keynote.add_shape`.
- [x] Test renderer stops on tool failure.
- [x] Test `RenderResult.tool_results` is populated.
- [x] Test CLI validates DeckSpec input.
- [x] Test CLI writes render metadata.
- [x] Test CLI writes `tool_results.jsonl` from `RenderResult.tool_results`.
- [x] Test CLI does not call LLM.

## 6. Integration Smoke Test

- [x] Add opt-in Keynote integration smoke test.
- [x] Use Three Little Pigs DeckSpec fixture.
- [x] Render with real Keynote only when `RUN_KEYNOTE_INTEGRATION=1`.
- [x] Export PDF.
- [x] Assert PDF exists and has non-zero size.

## 7. Documentation

- [x] Update README with `oka render-storybook` example.
- [x] Update CLAUDE.md and AGENTS.md with renderer workflow.
- [x] Document renderer limitations: no images, rectangle-only shapes, no shape fill color.

## 8. Quality Bar

- [x] Run `uv run pytest`.
- [x] Run `uv run ruff check .`.
- [x] Confirm non-integration tests do not require Keynote or macOS Automation permissions.
