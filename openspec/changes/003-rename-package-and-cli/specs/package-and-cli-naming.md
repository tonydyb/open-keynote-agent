# Spec: Package and CLI Naming

## Current Names (before this change)

| Artifact | Old name |
|---|---|
| Python package directory | `src/open_mac_agent/` |
| Python import root | `open_mac_agent` |
| Installed package name | `open-mac-agent` |
| CLI entrypoint | `oma` |

## Target Names (after this change)

| Artifact | New name |
|---|---|
| Python package directory | `src/open_keynote_agent/` |
| Python import root | `open_keynote_agent` |
| Installed package name | `open-keynote-agent` |
| CLI entrypoint | `oka` |

The project slug `open-keynote-agent` and product name `Open Keynote Agent` were already established in change 002. This change makes the Python package and CLI consistent with those names.

## pyproject.toml After This Change

```toml
[project]
name = "open-keynote-agent"
description = "An open-source macOS agent for creating and editing Apple Keynote presentations."
authors = [{ name = "Open Keynote Agent" }]
keywords = ["macOS", "Keynote", "agent", "CLI", "AI"]

[project.scripts]
oka = "open_keynote_agent.cli:app"
```

## Historical Context

The `oma` command and `open_mac_agent` package were introduced in change 001 (`add-cli-file-organizer`) under the earlier project name `open-mac-agent`. Change 002 repositioned the project as `Open Keynote Agent` but deferred this mechanical rename. This change completes what change 002 deferred.

## Invariants

- The `oka` command is the sole supported CLI entrypoint after this change.
- All Python code imports from `open_keynote_agent`, not `open_mac_agent`.
- Behavior, commands, options, and output format are unchanged except for the strings that print the product name or command name.
