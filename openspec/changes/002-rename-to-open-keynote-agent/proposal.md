# Proposal: Rename Project Focus to Open Keynote Agent

## Summary

Reposition the project from a broad macOS agent learning project (`open-mac-agent`) to a focused Keynote automation agent (`open-keynote-agent`).

The project should specialize in helping users create, modify, verify, and export Apple Keynote presentations through natural-language, step-by-step agent workflows.

## Motivation

The current `open-mac-agent` scope is too broad for the next learning phase. A general macOS agent implies support for many applications, UI automation methods, permissions, and workflows at once.

Keynote is a better focused domain because it still teaches the core desktop-agent concepts:

- interactive user instructions
- session state
- tool calling
- planner/executor separation
- native macOS automation
- human approval before mutation
- export and verification

But it keeps the product boundary narrow enough to build and test.

## Goals

- Rename the project positioning to `Open Keynote Agent`.
- Update README and OpenSpec project documentation.
- Define the new product direction: agent-assisted Keynote creation and editing.
- Preserve the existing CLI file organizer as a completed learning milestone, not the long-term product focus.
- Avoid renaming Python package names, CLI commands, or repository files in this change unless needed for documentation consistency.

## Non-Goals

- Do not implement Keynote automation yet.
- Do not introduce AppleScript, JXA, Accessibility API, or GUI automation in this change.
- Did not rename the package, distribution name, CLI command, or git repository (done in change 003).
- Do not remove the existing file organizer implementation.

## User Impact

Users and contributors should understand that future work is focused on building a Keynote-specific desktop agent rather than a general macOS automation framework.
