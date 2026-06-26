# Tasks

## 1. Deck Package And Schema

- [x] Add `src/open_keynote_agent/deck/__init__.py`.
- [x] Add `src/open_keynote_agent/deck/schema.py`.
- [x] Define `StyleSpec`.
- [x] Define `VisualSpec`.
- [x] Define `SlideSpec`.
- [x] Define `DeckSpec`.
- [x] Set `model_config = {"extra": "forbid"}` on all DeckSpec-related models.
- [x] Use `Field(default_factory=list)` for list defaults.
- [x] Validate non-empty `DeckSpec.title`.
- [x] Validate non-empty `StyleSpec.mood`.
- [x] Validate non-empty `SlideSpec.title`.
- [x] Validate non-empty `VisualSpec.description`.
- [x] Validate every `VisualSpec.emoji` item is a non-empty string.
- [x] Validate every `VisualSpec.decorations` item is a non-empty string.
- [x] Set `DeckSpec.language` default to `None`.
- [x] Validate slide count range `1..20`.
- [x] Validate slide indexes are sequential starting at 1.
- [x] Validate every slide has a visual spec.
- [x] Add unit tests for valid schemas.
- [x] Add unit tests for invalid schemas.

## 2. Deck Planner

- [x] Add `src/open_keynote_agent/deck/planner.py`.
- [x] Implement `plan_deck_spec(brief, llm_client, slide_count_hint=None, theme_hint="Parchment")`.
- [x] Reject blank briefs before calling the LLM.
- [x] Reject `slide_count_hint` outside `1..20` before calling the LLM.
- [x] Build a concise system prompt for structured deck planning.
- [x] Include theme and slide-count hints in planner messages.
- [x] Instruct the LLM to infer `language` from the brief's primary language.
- [x] Pass `DeckSpec.model_json_schema()` to `LLMClient.complete_json`.
- [x] Validate model output with `DeckSpec.model_validate(raw)`.
- [x] Ensure planner does not import or call Keynote tools.
- [x] Add tests with `FakeLLMClient`.
- [x] Add tests proving validation failures are surfaced clearly.
- [x] Add tests proving pre-LLM validation failures do not call `FakeLLMClient`.

## 3. Outline Renderer

- [x] Add `src/open_keynote_agent/deck/outline.py`.
- [x] Implement `render_deck_outline(deck)`.
- [x] Include deck title, subtitle, theme, and style.
- [x] Include slide index, kind, title, body bullets, and visuals.
- [x] Include emoji and decorations when present.
- [x] Keep outline output deterministic for tests.
- [x] Add unit tests for outline output.

## 4. CLI Command

- [x] Add `oka deck-plan "<brief>"`.
- [x] Add `--slides` option.
- [x] Add `--theme` option defaulting to `Parchment`.
- [x] Add `--output` option for output directory.
- [x] Use a unique default output directory under `.runs/<YYYYMMDDTHHMMSSZ>/` when `--output` is omitted.
- [x] Add `-1`, `-2`, etc. suffixes on default output directory timestamp collisions.
- [x] Refuse to overwrite existing `request.json`, `deck_spec.json`, or `outline.md`.
- [x] Write `request.json`.
- [x] Write `deck_spec.json` with `ensure_ascii=False`.
- [x] Write `outline.md`.
- [x] Print outline to terminal.
- [x] On LLM load/completion or validation failure, exit non-zero with a concise error.
- [x] On failure, do not write partial `request.json`, `deck_spec.json`, or `outline.md`.
- [x] On failure with default output, clean up any partially-created default output directory.
- [x] Confirm command does not open Keynote and does not call `keynote.*` tools.
- [x] Add CLI tests with `FakeLLMClient`.
- [x] Add CLI overwrite-refusal test.
- [x] Add CLI failure-behavior tests.

## 5. Three Little Pigs Fixture

- [x] Add a test fixture or example prompt for the Three Little Pigs deck.
- [x] Verify the fake DeckSpec has 7-8 slides.
- [x] Verify every slide includes visual metadata.
- [x] Verify style avoids blue/business direction when requested.
- [x] Verify theme defaults or hints prefer `Parchment`.

## 6. Documentation

- [x] Update README with `oka deck-plan` example.
- [x] Update CLAUDE.md and AGENTS.md with DeckSpec planning workflow.
- [x] Document that this change does not render Keynote slides yet.
- [x] Document that `VisualSpec.decorations` are conceptual notes, not direct `keynote.add_shape` enum values.

## 7. Quality Bar

- [x] Run `uv run pytest`.
- [x] Run `uv run ruff check .`.
- [x] Confirm tests do not require real LLM credentials, Keynote, `osascript`, or macOS Automation permissions.
