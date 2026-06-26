# Proposal: Add Keynote Theme and Layout Discovery

## Summary

Add Keynote discovery tools for listing installed themes, creating documents with a selected theme, listing slide layouts in the front document, and resolving semantic layout names to real Keynote layout names.

This change makes the Keynote adapter more portable across MacBooks and Keynote versions. It prepares the project for deterministic deck rendering using built-in Keynote themes such as `Parchment`.

## Motivation

Change 005 proved that the agent can control Keynote through AppleScript, but it also exposed a portability issue: layout names vary by Keynote theme. A semantic layout such as `title_body` may map to `Title & Bullets` in one theme and a different layout name in another.

For an open-source project, users should be able to download the repository and generate similar decks on their own MacBooks without installing custom themes. The adapter therefore needs a discovery layer:

- list available Keynote themes
- create a document with a built-in theme
- list slide layouts for the current document
- resolve semantic layout names to real Keynote layout names

## Goals

- Add AppleScript builders for listing themes and slide layouts.
- Add optional theme support to `keynote.create_document`.
- Add `keynote.list_themes`.
- Add `keynote.list_layouts`.
- Add `keynote.resolve_layout`.
- Update `keynote.add_slide` to resolve semantic layout names against the current document's actual layouts before running AppleScript.
- Keep `demo.*` tools unchanged.
- Keep tests deterministic with `FakeScriptRunner`.
- Preserve `Parchment` as the recommended built-in storybook-like theme when available.

## Non-Goals

- Do not build the full storybook deck renderer in this change.
- Do not add image insertion.
- Do not add object-level text box or shape tools.
- Do not require custom user-installed themes.
- Do not introduce GUI automation or Accessibility API.
- Do not make real Keynote integration tests run by default.

## User Impact

Users can ask the agent what Keynote themes and layouts are available, create a document with a built-in theme, and rely on semantic layout names instead of memorizing exact Keynote layout names.

Example:

```text
oka> Use tool keynote.list_themes
oka> Use tool keynote.create_document with name three-pigs and theme Parchment
oka> Use tool keynote.list_layouts
oka> Use tool keynote.add_slide with layout title_body
```

The adapter should map `title_body` to the best matching layout in the current document, such as `Title & Bullets`.

## Success Criteria

- Existing tests continue to pass.
- New unit tests cover theme listing, layout listing, theme-based document creation, and semantic layout resolution.
- `keynote.create_document` supports optional `theme`.
- `keynote.add_slide layout=title_body` works against the current document's discovered layouts when possible.
- Tests do not require Keynote or `osascript`.
- Real Keynote integration tests remain opt-in via `RUN_KEYNOTE_INTEGRATION=1`.
