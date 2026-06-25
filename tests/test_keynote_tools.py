"""Tests for the Keynote AppleScript adapter (005-add-keynote-applescript-adapter).

Unit tests only — no real osascript, no Keynote process, no macOS GUI access required.
subprocess is only monkeypatched through open_keynote_agent.applescript.runner.subprocess.run
in OsascriptRunner tests.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

import open_keynote_agent.cli as cli_module
from open_keynote_agent.agent.executor import execute_plan
from open_keynote_agent.agent.registry import ToolRegistry
from open_keynote_agent.agent.session import Plan, ProposedToolCall, SessionState
from open_keynote_agent.applescript import scripts
from open_keynote_agent.applescript.runner import (
    FakeScriptRunner,
    OsascriptRunner,
    ScriptRunResult,
)
from open_keynote_agent.cli import app
from open_keynote_agent.llm.fake import FakeLLMClient
from open_keynote_agent.tools.keynote import register_keynote_tools

cli_runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _registry_with_keynote(runner: FakeScriptRunner) -> ToolRegistry:
    registry = ToolRegistry()
    register_keynote_tools(registry, runner)
    return registry


def _run_tool(tool: str, args: dict[str, Any], runner: FakeScriptRunner) -> Any:
    registry = _registry_with_keynote(runner)
    state = SessionState()
    plan = Plan(steps=[ProposedToolCall(tool=tool, args=args, description=tool)])
    results = execute_plan(plan, registry, state)
    return results[0], state


# ---------------------------------------------------------------------------
# FakeScriptRunner
# ---------------------------------------------------------------------------

class TestFakeScriptRunner:
    def test_records_calls(self):
        fake = FakeScriptRunner()
        fake.run("script one")
        fake.run("script two")
        assert fake.calls == ["script one", "script two"]

    def test_default_success_response(self):
        fake = FakeScriptRunner()
        result = fake.run("anything")
        assert result.ok is True
        assert result.stdout == ""
        assert result.stderr == ""
        assert result.returncode == 0

    def test_exact_match_response(self):
        configured = ScriptRunResult(stdout="hello", stderr="", returncode=0)
        fake = FakeScriptRunner(responses={"my script": configured})
        result = fake.run("my script")
        assert result.stdout == "hello"

    def test_no_match_returns_default(self):
        configured = ScriptRunResult(stdout="hello", stderr="", returncode=0)
        fake = FakeScriptRunner(responses={"other": configured})
        result = fake.run("unmatched")
        assert result.ok is True
        assert result.stdout == ""

    def test_error_response(self):
        error = ScriptRunResult(stdout="", stderr="oops", returncode=1)
        fake = FakeScriptRunner(responses={"bad": error})
        result = fake.run("bad")
        assert result.ok is False
        assert result.stderr == "oops"


# ---------------------------------------------------------------------------
# OsascriptRunner (subprocess monkeypatched)
# ---------------------------------------------------------------------------

class TestOsascriptRunner:
    def test_successful_run(self, monkeypatch: pytest.MonkeyPatch):
        mock_proc = MagicMock()
        mock_proc.stdout = "output"
        mock_proc.stderr = ""
        mock_proc.returncode = 0
        import open_keynote_agent.applescript.runner as runner_mod
        monkeypatch.setattr(runner_mod.subprocess, "run", lambda *a, **kw: mock_proc)
        runner = OsascriptRunner()
        result = runner.run("tell application \"Keynote\" to activate")
        assert result.ok is True
        assert result.stdout == "output"

    def test_nonzero_returncode_returned_as_is(self, monkeypatch: pytest.MonkeyPatch):
        mock_proc = MagicMock()
        mock_proc.stdout = ""
        mock_proc.stderr = "error detail"
        mock_proc.returncode = 1
        import open_keynote_agent.applescript.runner as runner_mod
        monkeypatch.setattr(runner_mod.subprocess, "run", lambda *a, **kw: mock_proc)
        runner = OsascriptRunner()
        result = runner.run("bad script")
        assert result.ok is False
        assert result.stderr == "error detail"

    def test_timeout_raises_runtime_error(self, monkeypatch: pytest.MonkeyPatch):
        import subprocess as _subprocess
        import open_keynote_agent.applescript.runner as runner_mod

        def timeout_side_effect(*a, **kw):
            raise _subprocess.TimeoutExpired(cmd=["osascript"], timeout=30)

        monkeypatch.setattr(runner_mod.subprocess, "run", timeout_side_effect)
        runner = OsascriptRunner()
        with pytest.raises(RuntimeError, match="osascript timed out"):
            runner.run("slow script")


# ---------------------------------------------------------------------------
# AppleScript string escaping
# ---------------------------------------------------------------------------

class TestApplescriptString:
    def test_safe_string_unchanged(self):
        assert scripts.applescript_string("hello world") == "hello world"

    def test_escapes_double_quote(self):
        assert scripts.applescript_string('say "hi"') == 'say \\"hi\\"'

    def test_escapes_backslash(self):
        assert scripts.applescript_string("path\\to\\file") == "path\\\\to\\\\file"

    def test_escapes_both(self):
        result = scripts.applescript_string('C:\\Users\\"Alice"')
        assert "\\\\" in result
        assert '\\"' in result


# ---------------------------------------------------------------------------
# Script builders
# ---------------------------------------------------------------------------

class TestScriptBuilders:
    def test_create_document_contains_keynote(self):
        s = scripts.create_document("My Deck")
        assert "Keynote" in s
        assert "make new document" in s
        # name is session-only; Keynote document name is read-only, not set in AppleScript
        assert "My Deck" not in s

    def test_create_document_does_not_raise_on_special_chars(self):
        # Builder must not raise even when name contains characters that need escaping
        s = scripts.create_document('Doc"With\\Backslash')
        assert "make new document" in s

    def test_add_slide_contains_master(self):
        s = scripts.add_slide("Title, Content")
        assert "Keynote" in s
        assert "Title, Content" in s
        assert "slide" in s.lower()

    def test_add_slide_escapes_master_name(self):
        s = scripts.add_slide('Master"Name')
        assert '\\"' in s

    def test_set_slide_title_contains_slide_and_title(self):
        s = scripts.set_slide_title(2, "Hello World")
        assert "Keynote" in s
        assert "slide 2" in s
        assert "Hello World" in s
        assert "title" in s.lower()

    def test_set_slide_title_escapes_title(self):
        s = scripts.set_slide_title(1, 'Title "quoted"')
        assert '\\"' in s

    def test_set_slide_body_contains_slide_and_body(self):
        s = scripts.set_slide_body(3, "Body text")
        assert "Keynote" in s
        assert "slide 3" in s
        assert "Body text" in s
        assert "body" in s.lower()

    def test_set_slide_body_escapes_body(self):
        s = scripts.set_slide_body(1, 'body "here"')
        assert '\\"' in s

    def test_export_pdf_contains_path_and_pdf(self):
        s = scripts.export_pdf("/tmp/out.pdf")
        assert "Keynote" in s
        assert "/tmp/out.pdf" in s
        assert "PDF" in s

    def test_export_pdf_escapes_path(self):
        s = scripts.export_pdf('/tmp/"weird".pdf')
        assert '\\"' in s

    def test_get_document_info_returns_script(self):
        s = scripts.get_document_info()
        assert "Keynote" in s
        assert "|" in s
        assert "slide" in s.lower()

    def test_no_builder_contains_display_dialog(self):
        builders = [
            scripts.create_document("x"),
            scripts.add_slide("Title Slide"),
            scripts.set_slide_title(1, "t"),
            scripts.set_slide_body(1, "b"),
            scripts.export_pdf("/tmp/x.pdf"),
            scripts.get_document_info(),
        ]
        for b in builders:
            assert "display dialog" not in b


# ---------------------------------------------------------------------------
# Keynote tool handlers (via executor)
# ---------------------------------------------------------------------------

class TestCreateDocument:
    def test_success_updates_context(self):
        fake = FakeScriptRunner()
        result, state = _run_tool("keynote.create_document", {"name": "MyDeck"}, fake)
        assert result.ok is True
        assert state.context["keynote"]["name"] == "MyDeck"
        assert state.context["keynote"]["slide_count"] == 1

    def test_success_observation(self):
        fake = FakeScriptRunner()
        result, _ = _run_tool("keynote.create_document", {"name": "Deck"}, fake)
        assert "Deck" in result.observation

    def test_script_sent_to_runner(self):
        fake = FakeScriptRunner()
        _run_tool("keynote.create_document", {"name": "Deck"}, fake)
        assert len(fake.calls) == 1
        assert "Keynote" in fake.calls[0]

    def test_runner_error_produces_failed_result(self):
        fake = FakeScriptRunner()
        # Make any script call fail
        script = scripts.create_document("x")
        fake.responses[script] = ScriptRunResult(stdout="", stderr="permission denied", returncode=1)
        result, _ = _run_tool("keynote.create_document", {"name": "x"}, fake)
        assert result.ok is False
        assert "permission denied" in result.observation


class TestAddSlide:
    def test_valid_layout_title(self):
        fake = FakeScriptRunner()
        result, state = _run_tool("keynote.add_slide", {"layout": "title"}, fake)
        assert result.ok is True
        assert "Title Slide" in fake.calls[0]

    def test_valid_layout_title_body(self):
        fake = FakeScriptRunner()
        result, _ = _run_tool("keynote.add_slide", {"layout": "title_body"}, fake)
        assert result.ok is True
        assert "Title, Content" in fake.calls[0]

    def test_valid_layout_blank(self):
        fake = FakeScriptRunner()
        result, _ = _run_tool("keynote.add_slide", {"layout": "blank"}, fake)
        assert result.ok is True
        assert "Blank" in fake.calls[0]

    def test_invalid_layout_fails_before_runner(self):
        fake = FakeScriptRunner()
        result, _ = _run_tool("keynote.add_slide", {"layout": "unknown_layout"}, fake)
        assert result.ok is False
        assert len(fake.calls) == 0  # runner never called

    def test_slide_count_incremented(self):
        fake = FakeScriptRunner()
        registry = _registry_with_keynote(fake)
        state = SessionState()
        state.context["keynote"] = {"name": "d", "slide_count": 2}
        plan = Plan(steps=[ProposedToolCall(tool="keynote.add_slide", args={"layout": "blank"}, description="add")])
        execute_plan(plan, registry, state)
        assert state.context["keynote"]["slide_count"] == 3

    def test_runner_error_produces_failed_result(self):
        fake = FakeScriptRunner()
        script = scripts.add_slide("Blank")
        fake.responses[script] = ScriptRunResult(stdout="", stderr="Keynote error", returncode=1)
        result, _ = _run_tool("keynote.add_slide", {"layout": "blank"}, fake)
        assert result.ok is False


class TestSetSlideTitle:
    def test_success(self):
        fake = FakeScriptRunner()
        result, _ = _run_tool("keynote.set_slide_title", {"slide": 1, "title": "Hello"}, fake)
        assert result.ok is True
        assert "slide 1" in fake.calls[0]
        assert "Hello" in fake.calls[0]

    def test_observation_includes_slide_number(self):
        fake = FakeScriptRunner()
        result, _ = _run_tool("keynote.set_slide_title", {"slide": 3, "title": "x"}, fake)
        assert "3" in result.observation

    def test_runner_error_fails(self):
        fake = FakeScriptRunner()
        script = scripts.set_slide_title(1, "Hello")
        fake.responses[script] = ScriptRunResult(stdout="", stderr="no slide", returncode=1)
        result, _ = _run_tool("keynote.set_slide_title", {"slide": 1, "title": "Hello"}, fake)
        assert result.ok is False


class TestSetSlideBody:
    def test_success(self):
        fake = FakeScriptRunner()
        result, _ = _run_tool("keynote.set_slide_body", {"slide": 2, "body": "Content here"}, fake)
        assert result.ok is True
        assert "slide 2" in fake.calls[0]
        assert "Content here" in fake.calls[0]

    def test_runner_error_fails(self):
        fake = FakeScriptRunner()
        script = scripts.set_slide_body(2, "Content here")
        fake.responses[script] = ScriptRunResult(stdout="", stderr="error", returncode=1)
        result, _ = _run_tool("keynote.set_slide_body", {"slide": 2, "body": "Content here"}, fake)
        assert result.ok is False


class TestExportPdf:
    def test_success(self, tmp_path: Path):
        fake = FakeScriptRunner()
        out = tmp_path / "out.pdf"
        result, _ = _run_tool("keynote.export_pdf", {"path": str(out)}, fake)
        assert result.ok is True
        assert str(out) in result.observation

    def test_existing_path_fails_before_runner(self, tmp_path: Path):
        existing = tmp_path / "exists.pdf"
        existing.write_bytes(b"data")
        fake = FakeScriptRunner()
        result, _ = _run_tool("keynote.export_pdf", {"path": str(existing)}, fake)
        assert result.ok is False
        assert len(fake.calls) == 0

    def test_missing_parent_fails_before_runner(self, tmp_path: Path):
        missing_parent = tmp_path / "no_such_dir" / "out.pdf"
        fake = FakeScriptRunner()
        result, _ = _run_tool("keynote.export_pdf", {"path": str(missing_parent)}, fake)
        assert result.ok is False
        assert len(fake.calls) == 0

    def test_runner_error_fails(self, tmp_path: Path):
        out = tmp_path / "out.pdf"
        resolved = out.expanduser().resolve()
        fake = FakeScriptRunner()
        fake.responses[scripts.export_pdf(str(resolved))] = ScriptRunResult(
            stdout="", stderr="export failed", returncode=1
        )
        result, _ = _run_tool("keynote.export_pdf", {"path": str(out)}, fake)
        assert result.ok is False

    def test_script_uses_resolved_path(self, tmp_path: Path):
        fake = FakeScriptRunner()
        out = tmp_path / "out.pdf"
        _run_tool("keynote.export_pdf", {"path": str(out)}, fake)
        assert len(fake.calls) == 1
        # The resolved absolute path should appear in the script
        assert str(out.resolve()) in fake.calls[0]


class TestGetDocumentInfo:
    def test_parses_name_and_count(self):
        fake = FakeScriptRunner()
        script = scripts.get_document_info()
        fake.responses[script] = ScriptRunResult(stdout="MyDeck|3\n", stderr="", returncode=0)
        result, state = _run_tool("keynote.get_document_info", {}, fake)
        assert result.ok is True
        assert result.output["name"] == "MyDeck"
        assert result.output["slide_count"] == 3
        assert state.context["keynote"]["name"] == "MyDeck"
        assert state.context["keynote"]["slide_count"] == 3

    def test_updates_context(self):
        fake = FakeScriptRunner()
        script = scripts.get_document_info()
        fake.responses[script] = ScriptRunResult(stdout="Deck|5\n", stderr="", returncode=0)
        _, state = _run_tool("keynote.get_document_info", {}, fake)
        assert state.context["keynote"]["slide_count"] == 5

    def test_unparseable_output_fails(self):
        fake = FakeScriptRunner()
        script = scripts.get_document_info()
        fake.responses[script] = ScriptRunResult(stdout="garbled output no pipe", stderr="", returncode=0)
        result, _ = _run_tool("keynote.get_document_info", {}, fake)
        assert result.ok is False

    def test_runner_error_fails(self):
        fake = FakeScriptRunner()
        script = scripts.get_document_info()
        fake.responses[script] = ScriptRunResult(stdout="", stderr="no document", returncode=1)
        result, _ = _run_tool("keynote.get_document_info", {}, fake)
        assert result.ok is False
        assert "no document" in result.observation


# ---------------------------------------------------------------------------
# CLI --tools integration
# ---------------------------------------------------------------------------

class TestSessionToolsCLI:
    def test_default_uses_demo_tools(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        client = FakeLLMClient(response={
            "steps": [{"tool": "demo.create_document", "args": {"name": "x"}, "description": "create"}]
        })
        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: client)
        result = cli_runner.invoke(app, ["session", "--no-confirm"], input="create a deck\ndone\n")
        assert result.exit_code == 0
        assert "Created document" in result.output

    def test_explicit_demo_uses_demo_tools(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        client = FakeLLMClient(response={"steps": []})
        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: client)
        result = cli_runner.invoke(app, ["session", "--tools", "demo", "--no-confirm"], input="done\n")
        assert result.exit_code == 0

    def test_keynote_tools_registers_keynote(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake_runner = FakeScriptRunner()
        client = FakeLLMClient(response={
            "steps": [{"tool": "keynote.get_document_info", "args": {}, "description": "info"}]
        })
        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: client)

        # Intercept OsascriptRunner construction to inject FakeScriptRunner
        get_info_script = scripts.get_document_info()
        fake_runner.responses[get_info_script] = ScriptRunResult(
            stdout="TestDeck|2\n", stderr="", returncode=0
        )

        import open_keynote_agent.tools.keynote as keynote_mod
        original_register = keynote_mod.register_keynote_tools

        def patched_register(registry, runner):
            return original_register(registry, fake_runner)

        monkeypatch.setattr(cli_module, "register_keynote_tools", patched_register)
        result = cli_runner.invoke(app, ["session", "--tools", "keynote", "--no-confirm"], input="check\ndone\n")
        assert result.exit_code == 0
        assert "Automation" in result.output  # permission warning printed

    def test_keynote_prints_permission_warning(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        client = FakeLLMClient(response={"steps": []})
        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: client)

        fake_runner = FakeScriptRunner()
        import open_keynote_agent.tools.keynote as keynote_mod

        def patched_register(registry, runner):
            return keynote_mod.register_keynote_tools(registry, fake_runner)

        monkeypatch.setattr(cli_module, "register_keynote_tools", patched_register)
        result = cli_runner.invoke(app, ["session", "--tools", "keynote", "--no-confirm"], input="done\n")
        assert result.exit_code == 0
        assert "Automation" in result.output

    def test_invalid_tools_value_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        client = FakeLLMClient(response={"steps": []})
        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: client)
        result = cli_runner.invoke(app, ["session", "--tools", "invalid"])
        assert result.exit_code != 0

    def test_help_mentions_tools(self):
        result = cli_runner.invoke(app, ["session", "--help"])
        assert result.exit_code == 0
        assert "--tools" in result.output


# ---------------------------------------------------------------------------
# Integration tests (skipped unless RUN_KEYNOTE_INTEGRATION=1)
# ---------------------------------------------------------------------------

keynote_integration = pytest.mark.skipif(
    os.environ.get("RUN_KEYNOTE_INTEGRATION") != "1",
    reason="Set RUN_KEYNOTE_INTEGRATION=1 to run real Keynote integration tests",
)


@keynote_integration
@pytest.mark.keynote_integration
def test_keynote_smoke(tmp_path: Path):
    """Smoke test: create document -> add slide -> set title -> export PDF."""
    from open_keynote_agent.applescript.runner import OsascriptRunner as _OsascriptRunner

    registry = ToolRegistry()
    register_keynote_tools(registry, _OsascriptRunner())
    state = SessionState()

    def _step(tool, args):
        plan = Plan(steps=[ProposedToolCall(tool=tool, args=args, description=tool)])
        results = execute_plan(plan, registry, state)
        assert results[0].ok, f"{tool} failed: {results[0].error}"
        return results[0]

    _step("keynote.create_document", {"name": "smoke-test"})
    _step("keynote.add_slide", {"layout": "title_body"})
    _step("keynote.set_slide_title", {"slide": 1, "title": "Hello from oka"})

    pdf_path = tmp_path / "smoke.pdf"
    _step("keynote.export_pdf", {"path": str(pdf_path)})
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0
