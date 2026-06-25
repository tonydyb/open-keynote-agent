# Design: Open Keynote Agent Positioning

## New Product Direction

`Open Keynote Agent` is an open-source macOS agent focused on creating and editing Apple Keynote presentations through natural language.

The intended experience is interactive and step-by-step:

```text
user> Create a new product update deck.
agent> I will create a Keynote document with an opening slide. Apply? [y/N]

user> Add a slide explaining the architecture.
agent> I will add slide 2 with title and bullet content. Apply? [y/N]

user> Insert this diagram on slide 2.
agent> I will place the image on slide 2 and resize it. Apply? [y/N]

user> Export it to PDF.
agent> I will export the current document to PDF. Apply? [y/N]
```

## Existing Work

The existing CLI file organizer remains useful as the first learning milestone:

- LLM provider abstraction
- structured request validation
- deterministic local tools
- confirmation before mutation
- run logs
- tests without cloud credentials

However, it is no longer the long-term product center.

## Future Architecture Direction

Future changes should move toward:

```text
interactive session runtime
  -> planner
  -> tool registry
  -> executor
  -> observations
  -> session state
  -> run logs

keynote adapter
  -> AppleScript / JXA first
  -> Accessibility API fallback later
  -> export and verification tools
```

## Naming Decision

Documentation should use:

- Product name: `Open Keynote Agent`
- Project slug: `open-keynote-agent`

This change did not rename:

- Python package: `open_mac_agent`
- CLI command: `oma`
- repository directory

Those were handled in change 003 (`rename-package-and-cli`).

## Safety Principles

The narrower Keynote focus keeps the same safety principles:

- The LLM plans actions but does not directly mutate documents.
- Tools validate arguments before executing.
- Mutating Keynote operations require preview and approval.
- Export/write operations must avoid accidental overwrite unless explicitly approved.
- Each session records enough data to replay or debug what happened.
