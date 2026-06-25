# Proposal: Rename Python Package and CLI Command

## Summary

Rename the Python package from `open_mac_agent` to `open_keynote_agent` and the CLI entrypoint from `oma` to `oka`. Update all imports, references, and documentation to match.

## Motivation

The project is now positioned as `Open Keynote Agent`, a Keynote-specific desktop agent. The current package name `open_mac_agent` and CLI command `oma` reflect the earlier, broader `open-mac-agent` framing established before change 002. The names are now inconsistent with the documented product direction and project slug `open-keynote-agent`.

Renaming now, before the interactive agent runtime and Keynote tooling are added, is the lowest-risk time to make this change. The code surface is small, the existing behavior is simple, and the rename is mechanical.

## Goals

- Rename the Python package directory from `src/open_mac_agent/` to `src/open_keynote_agent/`.
- Update all import statements from `open_mac_agent` to `open_keynote_agent`.
- Update `pyproject.toml`: package name, description, authors, keywords, and CLI entrypoint.
- Rename the CLI entrypoint from `oma` to `oka`.
- Update all tests to import from `open_keynote_agent`.
- Update README, CLAUDE.md, AGENTS.md, and openspec documentation to use `oka` and `open_keynote_agent`.
- Keep all existing behavior unchanged.

## Non-Goals

- Do not implement the interactive agent runtime.
- Do not implement Keynote automation.
- Do not change any CLI commands, options, or output other than the entrypoint name.
- Do not rename the git repository directory.

## User Impact

Users and scripts that call `oma` must switch to `oka`. Python code that imports from `open_mac_agent` must switch to `open_keynote_agent`. No behavior changes.

## Risks

- Stale references left in any file will cause import errors or broken commands.
- The `.egg-info` directory under `src/` will still reference the old name until the package is reinstalled.

## Mitigations

- Enumerate every file that references `open_mac_agent` or `oma` before making changes.
- Reinstall the package with `uv sync` after renaming to regenerate entry points.
- Run `pytest` and `oka --help` after changes to confirm nothing is broken.

## Success Criteria

- `uv run oka --help` works.
- `uv run oka organize <folder> --dry-run` works.
- `uv run pytest` passes.
- `uv run ruff check .` passes.
- No file in the repository imports from `open_mac_agent` or references the `oma` entrypoint as the current command.
