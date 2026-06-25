# Tasks

## 1. Source Directory Rename

- [x] Rename `src/open_mac_agent/` to `src/open_keynote_agent/`.
- [x] Delete `src/open_mac_agent.egg-info/`.

## 2. pyproject.toml

- [x] Update `project.name` to `open-keynote-agent`.
- [x] Update `project.description` to reference Keynote automation.
- [x] Update `project.authors` to `Open Keynote Agent`.
- [x] Update `project.keywords` to include `Keynote`.
- [x] Update `project.scripts` key from `oma` to `oka`.
- [x] Update `project.scripts` value from `open_mac_agent.cli:app` to `open_keynote_agent.cli:app`.

## 3. Import Updates — Source Files

- [x] Update all `open_mac_agent` imports in `cli.py`.
- [x] Update all `open_mac_agent` imports in `filesystem.py`.
- [x] Update all `open_mac_agent` imports in `llm/__init__.py`.
- [x] Update all `open_mac_agent` imports in `llm/bedrock.py`.
- [x] Update all `open_mac_agent` imports in `llm/fake.py`.
- [x] Update all `open_mac_agent` imports in `llm/gemini.py`.
- [x] Update all `open_mac_agent` imports in `llm/json_utils.py`.
- [x] Update all `open_mac_agent` imports in `llm/openai.py`.
- [x] Update all `open_mac_agent` imports in `llm/parser.py`.
- [x] Update all `open_mac_agent` imports in `llm/schema.py`.
- [x] Update all `open_mac_agent` imports in `runtime/session.py`.

## 4. String Literals — cli.py

- [x] Update `version` command output from `open-mac-agent 0.1.0` to `open-keynote-agent 0.1.0`.
- [x] Update `hello` command message to reference `open-keynote-agent` and `oka`.
- [x] Update `create_run_session` calls from `"oma organize"` / `"oma ask"` to `"oka organize"` / `"oka ask"`.

## 5. Import Updates — Test Files

- [x] Update all `open_mac_agent` imports in `tests/test_cli.py`.
- [x] Update all `open_mac_agent` imports in `tests/test_filesystem.py`.
- [x] Update all `open_mac_agent` imports in `tests/test_llm.py`.
- [x] Update all `open_mac_agent` imports in `tests/test_llm_provider_adapters.py`.
- [x] Update all `open_mac_agent` imports in `tests/test_llm_providers.py`.
- [x] Update all `open_mac_agent` imports in `tests/test_organizer.py`.

## 6. Documentation Updates

- [x] Update `README.md`: replace all `oma` command examples with `oka`.
- [x] Update `CLAUDE.md`: replace all `oma` command examples with `oka`; update package/entrypoint references.
- [x] Update `AGENTS.md`: replace all `oma` command examples with `oka`; update package/entrypoint references.
- [x] Update `openspec/project.md`: note that package is now `open_keynote_agent` and CLI is now `oka`.
- [x] Update `openspec/changes/002-rename-to-open-keynote-agent/`: clarify that package/CLI rename is now done in change 003.

## 7. Reinstall and Verify

- [x] Run `uv sync` to reinstall and regenerate entry points.
- [x] Run `uv run oka --help` — must exit 0.
- [x] Run `uv run oka organize <tmp-folder> --dry-run` — must exit 0.
- [x] Run `uv run pytest` — all tests must pass.
- [x] Run `uv run ruff check .` — must pass with no errors.
- [x] Confirm no file imports from `open_mac_agent`.
