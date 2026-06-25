# Tasks

## 1. Source Directory Rename

- [ ] Rename `src/open_mac_agent/` to `src/open_keynote_agent/`.
- [ ] Delete `src/open_mac_agent.egg-info/`.

## 2. pyproject.toml

- [ ] Update `project.name` to `open-keynote-agent`.
- [ ] Update `project.description` to reference Keynote automation.
- [ ] Update `project.authors` to `Open Keynote Agent`.
- [ ] Update `project.keywords` to include `Keynote`.
- [ ] Update `project.scripts` key from `oma` to `oka`.
- [ ] Update `project.scripts` value from `open_mac_agent.cli:app` to `open_keynote_agent.cli:app`.

## 3. Import Updates — Source Files

- [ ] Update all `open_mac_agent` imports in `cli.py`.
- [ ] Update all `open_mac_agent` imports in `filesystem.py`.
- [ ] Update all `open_mac_agent` imports in `llm/__init__.py`.
- [ ] Update all `open_mac_agent` imports in `llm/bedrock.py`.
- [ ] Update all `open_mac_agent` imports in `llm/fake.py`.
- [ ] Update all `open_mac_agent` imports in `llm/gemini.py`.
- [ ] Update all `open_mac_agent` imports in `llm/json_utils.py`.
- [ ] Update all `open_mac_agent` imports in `llm/openai.py`.
- [ ] Update all `open_mac_agent` imports in `llm/parser.py`.
- [ ] Update all `open_mac_agent` imports in `llm/schema.py`.
- [ ] Update all `open_mac_agent` imports in `runtime/session.py`.

## 4. String Literals — cli.py

- [ ] Update `version` command output from `open-mac-agent 0.1.0` to `open-keynote-agent 0.1.0`.
- [ ] Update `hello` command message to reference `open-keynote-agent` and `oka`.
- [ ] Update `create_run_session` calls from `"oma organize"` / `"oma ask"` to `"oka organize"` / `"oka ask"`.

## 5. Import Updates — Test Files

- [ ] Update all `open_mac_agent` imports in `tests/test_cli.py`.
- [ ] Update all `open_mac_agent` imports in `tests/test_filesystem.py`.
- [ ] Update all `open_mac_agent` imports in `tests/test_llm.py`.
- [ ] Update all `open_mac_agent` imports in `tests/test_llm_provider_adapters.py`.
- [ ] Update all `open_mac_agent` imports in `tests/test_llm_providers.py`.
- [ ] Update all `open_mac_agent` imports in `tests/test_organizer.py`.

## 6. Documentation Updates

- [ ] Update `README.md`: replace all `oma` command examples with `oka`.
- [ ] Update `CLAUDE.md`: replace all `oma` command examples with `oka`; update package/entrypoint references.
- [ ] Update `AGENTS.md`: replace all `oma` command examples with `oka`; update package/entrypoint references.
- [ ] Update `openspec/project.md`: note that package is now `open_keynote_agent` and CLI is now `oka`.
- [ ] Update `openspec/changes/002-rename-to-open-keynote-agent/`: clarify that package/CLI rename is now done in change 003.

## 7. Reinstall and Verify

- [ ] Run `uv sync` to reinstall and regenerate entry points.
- [ ] Run `uv run oka --help` — must exit 0.
- [ ] Run `uv run oka organize <tmp-folder> --dry-run` — must exit 0.
- [ ] Run `uv run pytest` — all tests must pass.
- [ ] Run `uv run ruff check .` — must pass with no errors.
- [ ] Confirm no file imports from `open_mac_agent`.
