"""Tests for the Keynote AppleScript adapter (005 + 006).

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
from open_keynote_agent.applescript.layout import _parse_newline_list, resolve_layout_name
from open_keynote_agent.applescript.objects import (
    commit_object_id,
    generate_object_id,
    hex_to_rgb_tuple,
    validate_geometry,
    validate_object_id,
)
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


def _run_tool(tool: str, args: dict[str, Any], runner: FakeScriptRunner, context: dict[str, Any] | None = None) -> Any:
    registry = _registry_with_keynote(runner)
    state = SessionState()
    if context is not None:
        state.context.update(context)
    plan = Plan(steps=[ProposedToolCall(tool=tool, args=args, description=tool)])
    results = execute_plan(plan, registry, state)
    return results[0], state


_DEFAULT_LAYOUTS = ["Title", "Title & Bullets", "Blank"]


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
        assert result.stdout == "1"
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
        assert result.stdout == "1"

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
        s = scripts.add_slide("Title & Bullets")
        assert "Keynote" in s
        assert "Title & Bullets" in s
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

    def test_list_themes_contains_text_item_delimiters(self):
        s = scripts.list_themes()
        assert "text item delimiters" in s
        assert "Keynote" in s
        assert "theme" in s.lower()

    def test_list_themes_uses_newline_delimiter(self):
        s = scripts.list_themes()
        assert "\\n" in s

    def test_list_layouts_contains_text_item_delimiters(self):
        s = scripts.list_layouts()
        assert "text item delimiters" in s
        assert "Keynote" in s
        assert "master slide" in s

    def test_list_layouts_uses_newline_delimiter(self):
        s = scripts.list_layouts()
        assert "\\n" in s

    def test_create_document_with_theme(self):
        s = scripts.create_document("My Deck", theme="Parchment")
        assert "document theme" in s
        assert "Parchment" in s
        assert "My Deck" not in s  # name still session-only

    def test_create_document_with_theme_escapes_theme(self):
        s = scripts.create_document("x", theme='Theme"Name')
        assert '\\"' in s

    def test_create_document_without_theme_unchanged(self):
        s = scripts.create_document("x")
        assert "document theme" not in s
        assert "make new document" in s

    def test_no_builder_contains_display_dialog(self):
        builders = [
            scripts.list_themes(),
            scripts.list_layouts(),
            scripts.create_document("x"),
            scripts.create_document("x", theme="Parchment"),
            scripts.add_slide("Title"),
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
        script = scripts.create_document("x")
        fake.responses[script] = ScriptRunResult(stdout="", stderr="permission denied", returncode=1)
        result, _ = _run_tool("keynote.create_document", {"name": "x"}, fake)
        assert result.ok is False
        assert "permission denied" in result.observation

    def test_with_theme_updates_context_theme(self):
        fake = FakeScriptRunner()
        result, state = _run_tool("keynote.create_document", {"name": "MyDeck", "theme": "Parchment"}, fake)
        assert result.ok is True
        assert state.context["keynote"]["theme"] == "Parchment"

    def test_with_theme_script_contains_document_theme(self):
        fake = FakeScriptRunner()
        _run_tool("keynote.create_document", {"name": "x", "theme": "Parchment"}, fake)
        assert "document theme" in fake.calls[0]
        assert "Parchment" in fake.calls[0]

    def test_without_theme_no_document_theme_in_script(self):
        fake = FakeScriptRunner()
        _run_tool("keynote.create_document", {"name": "x"}, fake)
        assert "document theme" not in fake.calls[0]

    def test_without_theme_no_theme_in_context(self):
        fake = FakeScriptRunner()
        _, state = _run_tool("keynote.create_document", {"name": "x"}, fake)
        assert "theme" not in state.context.get("keynote", {})

    def test_preserves_themes_from_prior_list_themes(self):
        fake = FakeScriptRunner()
        ctx = {"keynote": {"themes": ["Parchment", "Basic White"]}}
        _, state = _run_tool("keynote.create_document", {"name": "x"}, fake, context=ctx)
        assert state.context["keynote"]["themes"] == ["Parchment", "Basic White"]

    def test_clears_stale_layouts_on_new_document(self):
        fake = FakeScriptRunner()
        ctx = {"keynote": {"layouts": ["Title", "Blank"], "themes": ["Parchment"]}}
        _, state = _run_tool("keynote.create_document", {"name": "x"}, fake, context=ctx)
        assert "layouts" not in state.context["keynote"]

    def test_with_theme_runner_error_does_not_set_context_theme(self):
        fake = FakeScriptRunner()
        script = scripts.create_document("x", theme="Parchment")
        fake.responses[script] = ScriptRunResult(stdout="", stderr="no theme", returncode=1)
        result, state = _run_tool("keynote.create_document", {"name": "x", "theme": "Parchment"}, fake)
        assert result.ok is False
        assert state.context.get("keynote", {}).get("theme") is None


class TestAddSlide:
    def test_valid_layout_title(self):
        fake = FakeScriptRunner()
        ctx = {"keynote": {"layouts": _DEFAULT_LAYOUTS}}
        result, state = _run_tool("keynote.add_slide", {"layout": "title"}, fake, context=ctx)
        assert result.ok is True
        # Only the add_slide script should have been called (no list_layouts)
        assert len(fake.calls) == 1
        assert "Title" in fake.calls[0]

    def test_valid_layout_title_body(self):
        fake = FakeScriptRunner()
        ctx = {"keynote": {"layouts": _DEFAULT_LAYOUTS}}
        result, _ = _run_tool("keynote.add_slide", {"layout": "title_body"}, fake, context=ctx)
        assert result.ok is True
        assert len(fake.calls) == 1
        assert "Title & Bullets" in fake.calls[0]

    def test_valid_layout_blank(self):
        fake = FakeScriptRunner()
        ctx = {"keynote": {"layouts": _DEFAULT_LAYOUTS}}
        result, _ = _run_tool("keynote.add_slide", {"layout": "blank"}, fake, context=ctx)
        assert result.ok is True
        assert len(fake.calls) == 1
        assert "Blank" in fake.calls[0]

    def test_does_not_call_list_layouts_when_cached(self):
        fake = FakeScriptRunner()
        ctx = {"keynote": {"layouts": _DEFAULT_LAYOUTS}}
        _run_tool("keynote.add_slide", {"layout": "title_body"}, fake, context=ctx)
        # Exactly one script call — add_slide only, not list_layouts
        assert len(fake.calls) == 1
        assert "master slide" in fake.calls[0]

    def test_calls_list_layouts_when_not_cached(self):
        fake = FakeScriptRunner()
        list_layouts_script = scripts.list_layouts()
        fake.responses[list_layouts_script] = ScriptRunResult(
            stdout="Title\nTitle & Bullets\nBlank\n", stderr="", returncode=0
        )
        result, state = _run_tool("keynote.add_slide", {"layout": "title_body"}, fake)
        assert result.ok is True
        # First call should be list_layouts, second is add_slide
        assert len(fake.calls) == 2
        assert fake.calls[0] == list_layouts_script
        assert "Title & Bullets" in fake.calls[1]
        # Context updated with fetched layouts
        assert state.context["keynote"]["layouts"] == ["Title", "Title & Bullets", "Blank"]

    def test_invalid_layout_fails(self):
        fake = FakeScriptRunner()
        ctx = {"keynote": {"layouts": _DEFAULT_LAYOUTS}}
        result, _ = _run_tool("keynote.add_slide", {"layout": "unknown_layout"}, fake, context=ctx)
        assert result.ok is False

    def test_slide_count_incremented(self):
        fake = FakeScriptRunner()
        registry = _registry_with_keynote(fake)
        state = SessionState()
        state.context["keynote"] = {"name": "d", "slide_count": 2, "layouts": _DEFAULT_LAYOUTS}
        plan = Plan(steps=[ProposedToolCall(tool="keynote.add_slide", args={"layout": "blank"}, description="add")])
        execute_plan(plan, registry, state)
        assert state.context["keynote"]["slide_count"] == 3

    def test_runner_error_produces_failed_result(self):
        fake = FakeScriptRunner()
        script = scripts.add_slide("Blank")
        fake.responses[script] = ScriptRunResult(stdout="", stderr="Keynote error", returncode=1)
        ctx = {"keynote": {"layouts": _DEFAULT_LAYOUTS}}
        result, _ = _run_tool("keynote.add_slide", {"layout": "blank"}, fake, context=ctx)
        assert result.ok is False


# ---------------------------------------------------------------------------
# Layout module: _parse_newline_list, LAYOUT_CANDIDATES, resolve_layout_name
# ---------------------------------------------------------------------------

class TestParseNewlineList:
    def test_basic(self):
        assert _parse_newline_list("Title\nTitle & Bullets\nBlank\n") == ["Title", "Title & Bullets", "Blank"]

    def test_empty_string(self):
        assert _parse_newline_list("") == []

    def test_strips_blank_lines(self):
        assert _parse_newline_list("Title\n\nBlank\n") == ["Title", "Blank"]

    def test_comma_containing_name_preserved(self):
        result = _parse_newline_list("Title\nTitle, Content\nBlank\n")
        assert result == ["Title", "Title, Content", "Blank"]

    def test_no_comma_splitting(self):
        # If comma-splitting happened, "Title, Content" would become two entries
        result = _parse_newline_list("Title, Content")
        assert len(result) == 1
        assert result[0] == "Title, Content"


class TestResolveLayoutName:
    def test_exact_match_returned(self):
        assert resolve_layout_name("Title & Bullets", ["Title", "Title & Bullets", "Blank"]) == "Title & Bullets"

    def test_semantic_title_resolves(self):
        assert resolve_layout_name("title", ["Title", "Title & Bullets", "Blank"]) == "Title"

    def test_semantic_title_body_resolves(self):
        assert resolve_layout_name("title_body", ["Title", "Title & Bullets", "Blank"]) == "Title & Bullets"

    def test_semantic_blank_resolves(self):
        assert resolve_layout_name("blank", ["Title", "Title & Bullets", "Blank"]) == "Blank"

    def test_first_candidate_wins(self):
        # "Title, Content" is a candidate for title_body; prefer it when "Title & Bullets" absent
        available = ["Title", "Title, Content", "Blank"]
        assert resolve_layout_name("title_body", available) == "Title, Content"

    def test_unknown_layout_raises_value_error(self):
        with pytest.raises(ValueError, match="nosuchlayout"):
            resolve_layout_name("nosuchlayout", ["Title", "Blank"])

    def test_error_includes_available(self):
        with pytest.raises(ValueError, match="Title"):
            resolve_layout_name("unknown", ["Title", "Blank"])

    def test_semantic_with_no_candidate_in_available_raises(self):
        with pytest.raises(ValueError):
            resolve_layout_name("title_body", ["Blank"])  # no title_body candidate present


class TestListThemesTool:
    def test_success_returns_themes(self):
        fake = FakeScriptRunner()
        fake.responses[scripts.list_themes()] = ScriptRunResult(
            stdout="Basic White\nParchment\nCraft\n", stderr="", returncode=0
        )
        result, state = _run_tool("keynote.list_themes", {}, fake)
        assert result.ok is True
        assert result.output["themes"] == ["Basic White", "Parchment", "Craft"]

    def test_updates_context(self):
        fake = FakeScriptRunner()
        fake.responses[scripts.list_themes()] = ScriptRunResult(
            stdout="Basic White\nParchment\n", stderr="", returncode=0
        )
        _, state = _run_tool("keynote.list_themes", {}, fake)
        assert state.context["keynote"]["themes"] == ["Basic White", "Parchment"]

    def test_observation_includes_count(self):
        fake = FakeScriptRunner()
        fake.responses[scripts.list_themes()] = ScriptRunResult(
            stdout="Basic White\nParchment\n", stderr="", returncode=0
        )
        result, _ = _run_tool("keynote.list_themes", {}, fake)
        assert "2" in result.observation

    def test_runner_error_fails(self):
        fake = FakeScriptRunner()
        fake.responses[scripts.list_themes()] = ScriptRunResult(stdout="", stderr="no Keynote", returncode=1)
        result, _ = _run_tool("keynote.list_themes", {}, fake)
        assert result.ok is False

    def test_no_osascript_called(self):
        fake = FakeScriptRunner()
        fake.responses[scripts.list_themes()] = ScriptRunResult(stdout="Parchment\n", stderr="", returncode=0)
        _run_tool("keynote.list_themes", {}, fake)
        # FakeScriptRunner proves no real subprocess was involved


class TestListLayoutsTool:
    def test_success_returns_layouts(self):
        fake = FakeScriptRunner()
        fake.responses[scripts.list_layouts()] = ScriptRunResult(
            stdout="Title\nTitle & Bullets\nBlank\n", stderr="", returncode=0
        )
        result, state = _run_tool("keynote.list_layouts", {}, fake)
        assert result.ok is True
        assert result.output["layouts"] == ["Title", "Title & Bullets", "Blank"]

    def test_updates_context(self):
        fake = FakeScriptRunner()
        fake.responses[scripts.list_layouts()] = ScriptRunResult(
            stdout="Title\nTitle & Bullets\nBlank\n", stderr="", returncode=0
        )
        _, state = _run_tool("keynote.list_layouts", {}, fake)
        assert state.context["keynote"]["layouts"] == ["Title", "Title & Bullets", "Blank"]

    def test_comma_containing_name_preserved(self):
        fake = FakeScriptRunner()
        fake.responses[scripts.list_layouts()] = ScriptRunResult(
            stdout="Title\nTitle, Content\nBlank\n", stderr="", returncode=0
        )
        result, state = _run_tool("keynote.list_layouts", {}, fake)
        assert "Title, Content" in result.output["layouts"]
        assert len(result.output["layouts"]) == 3

    def test_runner_error_fails(self):
        fake = FakeScriptRunner()
        fake.responses[scripts.list_layouts()] = ScriptRunResult(stdout="", stderr="no document", returncode=1)
        result, _ = _run_tool("keynote.list_layouts", {}, fake)
        assert result.ok is False


class TestResolveLayoutTool:
    def test_uses_cached_layouts(self):
        fake = FakeScriptRunner()
        ctx = {"keynote": {"layouts": _DEFAULT_LAYOUTS}}
        result, _ = _run_tool("keynote.resolve_layout", {"layout": "title_body"}, fake, context=ctx)
        assert result.ok is True
        assert result.output["resolved"] == "Title & Bullets"
        # No list_layouts call needed
        assert len(fake.calls) == 0

    def test_fetches_layouts_when_absent(self):
        fake = FakeScriptRunner()
        fake.responses[scripts.list_layouts()] = ScriptRunResult(
            stdout="Title\nTitle & Bullets\nBlank\n", stderr="", returncode=0
        )
        result, state = _run_tool("keynote.resolve_layout", {"layout": "title_body"}, fake)
        assert result.ok is True
        assert result.output["resolved"] == "Title & Bullets"
        assert fake.calls[0] == scripts.list_layouts()
        assert state.context["keynote"]["layouts"] == ["Title", "Title & Bullets", "Blank"]

    def test_unknown_layout_fails(self):
        fake = FakeScriptRunner()
        ctx = {"keynote": {"layouts": _DEFAULT_LAYOUTS}}
        result, _ = _run_tool("keynote.resolve_layout", {"layout": "nosuch"}, fake, context=ctx)
        assert result.ok is False

    def test_observation_includes_resolved_name(self):
        fake = FakeScriptRunner()
        ctx = {"keynote": {"layouts": _DEFAULT_LAYOUTS}}
        result, _ = _run_tool("keynote.resolve_layout", {"layout": "title_body"}, fake, context=ctx)
        assert "Title & Bullets" in result.observation


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
# Object utilities (objects.py)
# ---------------------------------------------------------------------------

class TestValidateObjectId:
    def test_valid_ids(self):
        for oid in ("a", "slide_01_text_box_1", "abc123", "z" * 64):
            validate_object_id(oid)  # must not raise

    def test_rejects_uppercase(self):
        with pytest.raises(ValueError):
            validate_object_id("MyObject")

    def test_rejects_leading_digit(self):
        with pytest.raises(ValueError):
            validate_object_id("1abc")

    def test_rejects_too_long(self):
        with pytest.raises(ValueError):
            validate_object_id("a" + "b" * 64)  # 65 chars total

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            validate_object_id("")

    def test_rejects_spaces(self):
        with pytest.raises(ValueError):
            validate_object_id("my object")


class TestGenerateObjectId:
    def test_generates_first_id(self):
        ctx: dict = {}
        oid = generate_object_id(1, "text_box", ctx)
        assert oid == "slide_01_text_box_1"

    def test_increments_counter(self):
        ctx: dict = {}
        oid1 = generate_object_id(1, "text_box", ctx)
        commit_object_id(1, "text_box", ctx)
        oid2 = generate_object_id(1, "text_box", ctx)
        commit_object_id(1, "text_box", ctx)
        assert oid1 == "slide_01_text_box_1"
        assert oid2 == "slide_01_text_box_2"

    def test_different_kinds_independent(self):
        ctx: dict = {}
        t = generate_object_id(1, "text_box", ctx)
        e = generate_object_id(1, "emoji", ctx)
        assert t == "slide_01_text_box_1"
        assert e == "slide_01_emoji_1"

    def test_slide_zero_padded(self):
        ctx: dict = {}
        oid = generate_object_id(8, "shape", ctx)
        assert oid == "slide_08_shape_1"

    def test_stores_counters_in_context(self):
        ctx: dict = {}
        generate_object_id(2, "text_box", ctx)
        commit_object_id(2, "text_box", ctx)
        assert ctx["keynote"]["object_counters"]["slide_02_text_box"] == 1


class TestValidateGeometry:
    def test_valid(self):
        validate_geometry(1, 0, 0, 100, 50)  # must not raise

    def test_slide_zero_fails(self):
        with pytest.raises(ValueError, match="slide"):
            validate_geometry(0, 0, 0, 100, 50)

    def test_negative_x_fails(self):
        with pytest.raises(ValueError, match="x"):
            validate_geometry(1, -1, 0, 100, 50)

    def test_negative_y_fails(self):
        with pytest.raises(ValueError, match="y"):
            validate_geometry(1, 0, -1, 100, 50)

    def test_zero_width_fails(self):
        with pytest.raises(ValueError, match="width"):
            validate_geometry(1, 0, 0, 0, 50)

    def test_zero_height_fails(self):
        with pytest.raises(ValueError, match="height"):
            validate_geometry(1, 0, 0, 100, 0)

    def test_slide_exceeds_count_fails(self):
        with pytest.raises(ValueError, match="slide_count"):
            validate_geometry(5, 0, 0, 100, 50, slide_count=3)

    def test_slide_equal_count_ok(self):
        validate_geometry(3, 0, 0, 100, 50, slide_count=3)


class TestHexToRgbTuple:
    def test_white(self):
        assert hex_to_rgb_tuple("#FFFFFF") == (65535, 65535, 65535)

    def test_black(self):
        assert hex_to_rgb_tuple("#000000") == (0, 0, 0)

    def test_known_color(self):
        r, g, b = hex_to_rgb_tuple("#F6A04D")
        assert r == round(0xF6 * 65535 / 255)
        assert g == round(0xA0 * 65535 / 255)
        assert b == round(0x4D * 65535 / 255)

    def test_rejects_no_hash(self):
        with pytest.raises(ValueError):
            hex_to_rgb_tuple("FFFFFF")

    def test_rejects_short(self):
        with pytest.raises(ValueError):
            hex_to_rgb_tuple("#FFF")

    def test_rejects_invalid_hex_chars(self):
        with pytest.raises(ValueError):
            hex_to_rgb_tuple("#GGGGGG")


# ---------------------------------------------------------------------------
# Object AppleScript builders
# ---------------------------------------------------------------------------

class TestAddTextBoxBuilder:
    def test_contains_keynote_and_returns_index(self):
        s = scripts.add_text_box(1, "my_obj", "Hello", 10, 20, 200, 50)
        assert "Keynote" in s
        assert "return count of text items" in s
        assert "Hello" in s

    def test_does_not_use_keynote_object_name(self):
        s = scripts.add_text_box(1, "my_obj", "x", 0, 0, 100, 50)
        assert "object name" not in s
        assert "set name of" not in s

    def test_font_size_applied_to_paragraph(self):
        s = scripts.add_text_box(1, "o", "x", 0, 0, 100, 50, font_size=64)
        assert "every paragraph of object text" in s
        assert "64" in s

    def test_font_color_applied_to_paragraph(self):
        s = scripts.add_text_box(1, "o", "x", 0, 0, 100, 50, font_color=(65535, 0, 0))
        assert "text color" in s
        assert "every paragraph of object text" in s
        assert "65535" in s

    def test_no_font_color_when_none(self):
        s = scripts.add_text_box(1, "o", "x", 0, 0, 100, 50)
        assert "text color" not in s

    def test_escapes_text(self):
        s = scripts.add_text_box(1, "o", 'He said "hi"', 0, 0, 100, 50)
        assert '\\"' in s

    def test_escapes_object_id(self):
        s = scripts.add_text_box(1, 'id"bad', "x", 0, 0, 100, 50)
        assert '\\"' not in s  # object_id stays local; Keynote object names are unsupported

    def test_slide_number_present(self):
        s = scripts.add_text_box(3, "o", "x", 0, 0, 100, 50)
        assert "slide 3" in s


class TestAddShapeBuilder:
    def test_contains_keynote_and_returns_index(self):
        s = scripts.add_shape(1, "my_shape", "rectangle", 0, 0, 200, 100)
        assert "Keynote" in s
        assert "return count of shapes" in s

    def test_fill_color_rejected_by_builder(self):
        with pytest.raises(ValueError):
            scripts.add_shape(1, "s", "rectangle", 0, 0, 100, 50, fill_color=(65535, 0, 0))

    def test_no_fill_color_when_none(self):
        s = scripts.add_shape(1, "s", "rectangle", 0, 0, 100, 50)
        assert "fill color" not in s


class TestMoveObjectBuilder:
    def test_uses_stored_class_and_index(self):
        s = scripts.move_object(1, "text item", 7, 50, 80)
        assert "text item 7" in s

    def test_sets_position(self):
        s = scripts.move_object(1, "text item", 7, 50, 80)
        assert "position" in s
        assert "50" in s
        assert "80" in s


class TestResizeObjectBuilder:
    def test_uses_stored_class_and_index(self):
        s = scripts.resize_object(1, "shape", 3, 300, 150)
        assert "shape 3" in s

    def test_sets_width_and_height(self):
        s = scripts.resize_object(1, "text item", 7, 300, 150)
        assert "300" in s
        assert "150" in s


# ---------------------------------------------------------------------------
# keynote.add_text_box tool
# ---------------------------------------------------------------------------

class TestAddTextBoxTool:
    def _ctx_with_layouts(self):
        return {"keynote": {"layouts": _DEFAULT_LAYOUTS, "slide_count": 3}}

    def test_success_updates_context(self):
        fake = FakeScriptRunner()
        ctx = self._ctx_with_layouts()
        result, state = _run_tool(
            "keynote.add_text_box",
            {"slide": 1, "text": "The End", "x": 100, "y": 200, "width": 400, "height": 80,
             "object_id": "slide_01_the_end"},
            fake, context=ctx,
        )
        assert result.ok is True
        obj = state.context["keynote"]["objects"]["slide_01_the_end"]
        assert obj["slide"] == 1
        assert obj["type"] == "text_box"
        assert obj["apple_class"] == "text item"
        assert obj["apple_index"] == 1
        assert obj["text"] == "The End"
        assert obj["x"] == 100.0
        assert obj["y"] == 200.0
        assert obj["width"] == 400.0
        assert obj["height"] == 80.0

    def test_slides_index_uses_string_key(self):
        fake = FakeScriptRunner()
        ctx = self._ctx_with_layouts()
        _run_tool(
            "keynote.add_text_box",
            {"slide": 2, "text": "x", "x": 0, "y": 0, "width": 100, "height": 50,
             "object_id": "slide_02_x"},
            fake, context=ctx,
        )
        assert "2" in ctx["keynote"]["slides"]
        assert "slide_02_x" in ctx["keynote"]["slides"]["2"]["objects"]

    def test_auto_generates_object_id(self):
        fake = FakeScriptRunner()
        ctx = self._ctx_with_layouts()
        result, state = _run_tool(
            "keynote.add_text_box",
            {"slide": 1, "text": "Hi", "x": 0, "y": 0, "width": 100, "height": 50},
            fake, context=ctx,
        )
        assert result.ok is True
        assert result.output["object_id"] == "slide_01_text_box_1"

    def test_duplicate_object_id_rejected_before_runner(self):
        fake = FakeScriptRunner()
        ctx: dict = {"keynote": {"layouts": _DEFAULT_LAYOUTS, "slide_count": 3,
                                 "objects": {"myid": {"object_id": "myid", "slide": 1}}}}
        result, _ = _run_tool(
            "keynote.add_text_box",
            {"slide": 1, "text": "x", "x": 0, "y": 0, "width": 100, "height": 50,
             "object_id": "myid"},
            fake, context=ctx,
        )
        assert result.ok is False
        assert len(fake.calls) == 0

    def test_invalid_geometry_rejected_before_runner(self):
        fake = FakeScriptRunner()
        ctx = self._ctx_with_layouts()
        result, _ = _run_tool(
            "keynote.add_text_box",
            {"slide": 0, "text": "x", "x": 0, "y": 0, "width": 100, "height": 50},
            fake, context=ctx,
        )
        assert result.ok is False
        assert len(fake.calls) == 0

    def test_slide_exceeds_count_rejected_before_runner(self):
        fake = FakeScriptRunner()
        ctx = {"keynote": {"layouts": _DEFAULT_LAYOUTS, "slide_count": 2}}
        result, _ = _run_tool(
            "keynote.add_text_box",
            {"slide": 5, "text": "x", "x": 0, "y": 0, "width": 100, "height": 50},
            fake, context=ctx,
        )
        assert result.ok is False
        assert len(fake.calls) == 0

    def test_invalid_color_rejected_before_runner(self):
        fake = FakeScriptRunner()
        ctx = self._ctx_with_layouts()
        result, _ = _run_tool(
            "keynote.add_text_box",
            {"slide": 1, "text": "x", "x": 0, "y": 0, "width": 100, "height": 50,
             "font_color": "notacolor"},
            fake, context=ctx,
        )
        assert result.ok is False
        assert len(fake.calls) == 0

    def test_font_color_applied_in_script(self):
        fake = FakeScriptRunner()
        ctx = self._ctx_with_layouts()
        _run_tool(
            "keynote.add_text_box",
            {"slide": 1, "text": "x", "x": 0, "y": 0, "width": 100, "height": 50,
             "font_color": "#FF0000"},
            fake, context=ctx,
        )
        assert "text color" in fake.calls[0]
        assert "every paragraph of object text" in fake.calls[0]

    def test_script_does_not_use_object_name(self):
        fake = FakeScriptRunner()
        ctx = self._ctx_with_layouts()
        _run_tool(
            "keynote.add_text_box",
            {"slide": 1, "text": "x", "x": 0, "y": 0, "width": 100, "height": 50,
             "object_id": "slide_01_x"},
            fake, context=ctx,
        )
        assert "object name" not in fake.calls[0]
        assert "set name of" not in fake.calls[0]

    def test_runner_failure_does_not_register_object(self):
        fake = FakeScriptRunner()
        ctx: dict = {"keynote": {"layouts": _DEFAULT_LAYOUTS}}
        # Handlers coerce geometry args to float before passing to script builders;
        # use float values here so the key matches what the handler actually sends.
        s = scripts.add_text_box(1, "slide_01_text_box_1", "x", 0, 0, 100, 50)
        fake.responses[s] = ScriptRunResult("", "oops", 1)
        result, state = _run_tool(
            "keynote.add_text_box",
            {"slide": 1, "text": "x", "x": 0, "y": 0, "width": 100, "height": 50},
            fake, context=ctx,
        )
        assert result.ok is False
        assert "objects" not in state.context.get("keynote", {})


# ---------------------------------------------------------------------------
# keynote.add_emoji_text tool
# ---------------------------------------------------------------------------

class TestAddEmojiTextTool:
    def test_success_records_type_and_text(self):
        fake = FakeScriptRunner()
        ctx: dict = {"keynote": {"slide_count": 2}}
        result, state = _run_tool(
            "keynote.add_emoji_text",
            {"slide": 1, "emoji": "🐷", "x": 100, "y": 100, "size": 96,
             "object_id": "slide_01_pig"},
            fake, context=ctx,
        )
        assert result.ok is True
        obj = state.context["keynote"]["objects"]["slide_01_pig"]
        assert obj["type"] == "emoji"
        assert obj["apple_class"] == "text item"
        assert obj["apple_index"] == 1
        assert obj["text"] == "🐷"

    def test_size_maps_to_geometry(self):
        fake = FakeScriptRunner()
        ctx: dict = {}
        _, state = _run_tool(
            "keynote.add_emoji_text",
            {"slide": 1, "emoji": "🐷", "x": 0, "y": 0, "size": 96,
             "object_id": "slide_01_e"},
            fake, context=ctx,
        )
        obj = state.context["keynote"]["objects"]["slide_01_e"]
        assert obj["width"] == 96 * 1.5
        assert obj["height"] == 96 * 1.5

    def test_calls_text_box_path(self):
        fake = FakeScriptRunner()
        ctx: dict = {}
        _run_tool(
            "keynote.add_emoji_text",
            {"slide": 1, "emoji": "🐷", "x": 0, "y": 0, "size": 96,
             "object_id": "slide_01_e"},
            fake, context=ctx,
        )
        # Exactly one runner call using add_text_box AppleScript form
        assert len(fake.calls) == 1
        assert "object name" not in fake.calls[0]
        assert "🐷" in fake.calls[0]

    def test_size_zero_rejected_before_runner(self):
        fake = FakeScriptRunner()
        result, _ = _run_tool(
            "keynote.add_emoji_text",
            {"slide": 1, "emoji": "🐷", "x": 0, "y": 0, "size": 0},
            fake,
        )
        assert result.ok is False
        assert len(fake.calls) == 0

    def test_auto_generates_object_id_with_emoji_kind(self):
        fake = FakeScriptRunner()
        ctx: dict = {}
        result, _ = _run_tool(
            "keynote.add_emoji_text",
            {"slide": 3, "emoji": "🐺", "x": 0, "y": 0, "size": 64},
            fake, context=ctx,
        )
        assert result.ok is True
        assert result.output["object_id"] == "slide_03_emoji_1"

    def test_slides_index_uses_string_key(self):
        fake = FakeScriptRunner()
        ctx: dict = {}
        _, state = _run_tool(
            "keynote.add_emoji_text",
            {"slide": 2, "emoji": "🐷", "x": 0, "y": 0, "size": 48,
             "object_id": "slide_02_pig"},
            fake, context=ctx,
        )
        assert "2" in state.context["keynote"]["slides"]


# ---------------------------------------------------------------------------
# keynote.add_shape tool
# ---------------------------------------------------------------------------

class TestAddShapeTool:
    def test_rectangle_success(self):
        fake = FakeScriptRunner()
        ctx: dict = {"keynote": {"slide_count": 2}}
        result, state = _run_tool(
            "keynote.add_shape",
            {"slide": 1, "shape": "rectangle", "x": 0, "y": 0, "width": 200, "height": 100,
             "object_id": "slide_01_rect"},
            fake, context=ctx,
        )
        assert result.ok is True
        obj = state.context["keynote"]["objects"]["slide_01_rect"]
        assert obj["type"] == "shape"
        assert obj["apple_class"] == "shape"
        assert obj["apple_index"] == 1
        assert obj["shape"] == "rectangle"

    def test_rounded_rectangle_rejected_before_runner(self):
        fake = FakeScriptRunner()
        result, _ = _run_tool(
            "keynote.add_shape",
            {"slide": 1, "shape": "rounded_rectangle", "x": 0, "y": 0,
             "width": 200, "height": 100, "object_id": "slide_01_rr"},
            fake,
        )
        assert result.ok is False
        assert len(fake.calls) == 0

    def test_oval_rejected_before_runner(self):
        fake = FakeScriptRunner()
        result, _ = _run_tool(
            "keynote.add_shape",
            {"slide": 1, "shape": "oval", "x": 0, "y": 0,
             "width": 200, "height": 100, "object_id": "slide_01_oval"},
            fake,
        )
        assert result.ok is False
        assert len(fake.calls) == 0

    def test_line_rejected_before_runner(self):
        fake = FakeScriptRunner()
        result, _ = _run_tool(
            "keynote.add_shape",
            {"slide": 1, "shape": "line", "x": 0, "y": 0, "width": 200, "height": 5},
            fake,
        )
        assert result.ok is False
        assert len(fake.calls) == 0

    def test_unknown_shape_rejected_before_runner(self):
        fake = FakeScriptRunner()
        result, _ = _run_tool(
            "keynote.add_shape",
            {"slide": 1, "shape": "triangle", "x": 0, "y": 0, "width": 200, "height": 100},
            fake,
        )
        assert result.ok is False
        assert len(fake.calls) == 0

    def test_fill_color_rejected_before_runner(self):
        fake = FakeScriptRunner()
        result, _ = _run_tool(
            "keynote.add_shape",
            {"slide": 1, "shape": "rectangle", "x": 0, "y": 0, "width": 100, "height": 50,
             "object_id": "slide_01_s", "fill_color": "#F4D8A8"},
            fake,
        )
        assert result.ok is False
        assert len(fake.calls) == 0

    def test_fill_color_rejected_before_color_validation(self):
        fake = FakeScriptRunner()
        result, _ = _run_tool(
            "keynote.add_shape",
            {"slide": 1, "shape": "rectangle", "x": 0, "y": 0, "width": 100, "height": 50,
             "fill_color": "badcolor"},
            fake,
        )
        assert result.ok is False
        assert len(fake.calls) == 0

    def test_script_does_not_use_object_name(self):
        fake = FakeScriptRunner()
        _run_tool(
            "keynote.add_shape",
            {"slide": 1, "shape": "rectangle", "x": 0, "y": 0, "width": 100, "height": 50,
             "object_id": "slide_01_s"},
            fake,
        )
        assert "object name" not in fake.calls[0]

    def test_runner_failure_does_not_register(self):
        fake = FakeScriptRunner()
        ctx: dict = {}
        s = scripts.add_shape(1, "slide_01_shape_1", "rectangle", 0, 0, 100, 50)
        fake.responses[s] = ScriptRunResult("", "fail", 1)
        result, state = _run_tool(
            "keynote.add_shape",
            {"slide": 1, "shape": "rectangle", "x": 0, "y": 0, "width": 100, "height": 50},
            fake, context=ctx,
        )
        assert result.ok is False
        assert "objects" not in state.context.get("keynote", {})

    def test_context_unchanged_after_runner_failure(self):
        fake = FakeScriptRunner()
        ctx: dict = {"keynote": {"objects": {"existing": {"object_id": "existing", "slide": 1}}}}
        s = scripts.add_shape(1, "slide_01_shape_1", "rectangle", 0, 0, 100, 50)
        fake.responses[s] = ScriptRunResult("", "fail", 1)
        _, state = _run_tool(
            "keynote.add_shape",
            {"slide": 1, "shape": "rectangle", "x": 0, "y": 0, "width": 100, "height": 50},
            fake, context=ctx,
        )
        assert list(state.context["keynote"]["objects"].keys()) == ["existing"]


# ---------------------------------------------------------------------------
# keynote.move_object tool
# ---------------------------------------------------------------------------

class TestMoveObjectTool:
    def _ctx_with_object(self):
        return {
            "keynote": {
                "objects": {
                    "slide_01_box": {
                        "object_id": "slide_01_box",
                        "slide": 1,
                        "type": "text_box",
                        "x": 100.0,
                        "y": 200.0,
                        "width": 300.0,
                    "height": 80.0,
                    "apple_class": "text item",
                    "apple_index": 7,
                }
                },
                "slides": {"1": {"objects": ["slide_01_box"]}},
            }
        }

    def test_success_updates_context(self):
        fake = FakeScriptRunner()
        ctx = self._ctx_with_object()
        result, state = _run_tool(
            "keynote.move_object",
            {"object_id": "slide_01_box", "x": 50, "y": 60},
            fake, context=ctx,
        )
        assert result.ok is True
        obj = state.context["keynote"]["objects"]["slide_01_box"]
        assert obj["x"] == 50.0
        assert obj["y"] == 60.0

    def test_uses_stored_reference_in_script(self):
        fake = FakeScriptRunner()
        ctx = self._ctx_with_object()
        _run_tool("keynote.move_object", {"object_id": "slide_01_box", "x": 0, "y": 0},
                  fake, context=ctx)
        assert "text item 7" in fake.calls[0]

    def test_unknown_object_id_rejected_before_runner(self):
        fake = FakeScriptRunner()
        result, _ = _run_tool(
            "keynote.move_object",
            {"object_id": "nonexistent", "x": 0, "y": 0},
            fake,
        )
        assert result.ok is False
        assert len(fake.calls) == 0

    def test_runner_failure_does_not_mutate_context(self):
        fake = FakeScriptRunner()
        ctx = self._ctx_with_object()
        s = scripts.move_object(1, "text item", 7, 50, 60)
        fake.responses[s] = ScriptRunResult("", "move failed", 1)
        result, state = _run_tool(
            "keynote.move_object",
            {"object_id": "slide_01_box", "x": 50, "y": 60},
            fake, context=ctx,
        )
        assert result.ok is False
        # x, y unchanged
        assert state.context["keynote"]["objects"]["slide_01_box"]["x"] == 100.0
        assert state.context["keynote"]["objects"]["slide_01_box"]["y"] == 200.0

    def test_negative_x_rejected_before_runner(self):
        fake = FakeScriptRunner()
        ctx = self._ctx_with_object()
        result, _ = _run_tool(
            "keynote.move_object",
            {"object_id": "slide_01_box", "x": -1, "y": 0},
            fake, context=ctx,
        )
        assert result.ok is False
        assert len(fake.calls) == 0


# ---------------------------------------------------------------------------
# keynote.resize_object tool
# ---------------------------------------------------------------------------

class TestResizeObjectTool:
    def _ctx_with_object(self):
        return {
            "keynote": {
                "objects": {
                    "slide_01_box": {
                        "object_id": "slide_01_box",
                        "slide": 1,
                        "type": "text_box",
                        "x": 100.0,
                        "y": 200.0,
                        "width": 300.0,
                        "height": 80.0,
                        "apple_class": "text item",
                        "apple_index": 7,
                    }
                }
            }
        }

    def test_success_updates_context(self):
        fake = FakeScriptRunner()
        ctx = self._ctx_with_object()
        result, state = _run_tool(
            "keynote.resize_object",
            {"object_id": "slide_01_box", "width": 500, "height": 120},
            fake, context=ctx,
        )
        assert result.ok is True
        obj = state.context["keynote"]["objects"]["slide_01_box"]
        assert obj["width"] == 500.0
        assert obj["height"] == 120.0

    def test_uses_stored_reference_in_script(self):
        fake = FakeScriptRunner()
        ctx = self._ctx_with_object()
        _run_tool("keynote.resize_object", {"object_id": "slide_01_box", "width": 200, "height": 100},
                  fake, context=ctx)
        assert "text item 7" in fake.calls[0]

    def test_unknown_object_id_rejected_before_runner(self):
        fake = FakeScriptRunner()
        result, _ = _run_tool(
            "keynote.resize_object",
            {"object_id": "ghost", "width": 200, "height": 100},
            fake,
        )
        assert result.ok is False
        assert len(fake.calls) == 0

    def test_zero_width_rejected_before_runner(self):
        fake = FakeScriptRunner()
        ctx = self._ctx_with_object()
        result, _ = _run_tool(
            "keynote.resize_object",
            {"object_id": "slide_01_box", "width": 0, "height": 100},
            fake, context=ctx,
        )
        assert result.ok is False
        assert len(fake.calls) == 0

    def test_runner_failure_does_not_mutate_context(self):
        fake = FakeScriptRunner()
        ctx = self._ctx_with_object()
        s = scripts.resize_object(1, "text item", 7, 500, 120)
        fake.responses[s] = ScriptRunResult("", "resize failed", 1)
        result, state = _run_tool(
            "keynote.resize_object",
            {"object_id": "slide_01_box", "width": 500, "height": 120},
            fake, context=ctx,
        )
        assert result.ok is False
        assert state.context["keynote"]["objects"]["slide_01_box"]["width"] == 300.0
        assert state.context["keynote"]["objects"]["slide_01_box"]["height"] == 80.0


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
    """Smoke test: list_themes -> create document with theme -> list_layouts -> add_slide -> set_title -> export PDF."""
    from open_keynote_agent.applescript.runner import OsascriptRunner as _OsascriptRunner

    registry = ToolRegistry()
    register_keynote_tools(registry, _OsascriptRunner())
    state = SessionState()

    def _step(tool, args):
        plan = Plan(steps=[ProposedToolCall(tool=tool, args=args, description=tool)])
        results = execute_plan(plan, registry, state)
        assert results[0].ok, f"{tool} failed: {results[0].error}"
        return results[0]

    # 1. List themes and choose Parchment > Basic White > first available
    themes_result = _step("keynote.list_themes", {})
    themes = themes_result.output["themes"]
    assert len(themes) > 0, "No themes returned"
    if "Parchment" in themes:
        chosen_theme = "Parchment"
    elif "Basic White" in themes:
        chosen_theme = "Basic White"
    else:
        chosen_theme = themes[0]
    print(f"Using theme: {chosen_theme!r}")

    # 2. Create document with chosen theme
    _step("keynote.create_document", {"name": "smoke-test", "theme": chosen_theme})
    assert state.context["keynote"]["theme"] == chosen_theme

    # 3. List layouts
    layouts_result = _step("keynote.list_layouts", {})
    layouts = layouts_result.output["layouts"]
    assert len(layouts) > 0, "No layouts returned"
    print(f"Layouts: {layouts}")

    # 4. Add a title_body slide through semantic resolution
    _step("keynote.add_slide", {"layout": "title_body"})

    # 5. Set title on slide 1
    _step("keynote.set_slide_title", {"slide": 1, "title": "Hello from oka"})

    # 6. Add a text box
    _step("keynote.add_text_box", {
        "slide": 1, "text": "The End", "x": 360, "y": 260,
        "width": 560, "height": 110, "object_id": "slide_01_the_end",
        "font_size": 64,
    })

    # 7. Add an emoji text object
    _step("keynote.add_emoji_text", {
        "slide": 1, "emoji": "🐷", "x": 760, "y": 180, "size": 96,
        "object_id": "slide_01_pig",
    })

    # 8. Add the MVP rectangle shape. Other shape kinds/fill colors are deferred
    # until a real Keynote AppleScript construction path is confirmed.
    _step("keynote.add_shape", {
        "slide": 1, "shape": "rectangle", "x": 50, "y": 50,
        "width": 300, "height": 150, "object_id": "slide_01_rect",
    })

    # 9. Resize one object
    _step("keynote.resize_object", {"object_id": "slide_01_the_end", "width": 660, "height": 140})
    assert state.context["keynote"]["objects"]["slide_01_the_end"]["width"] == 660.0

    # 10. Export PDF
    pdf_path = tmp_path / "smoke.pdf"
    _step("keynote.export_pdf", {"path": str(pdf_path)})
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0


# ---------------------------------------------------------------------------
# scripts.add_image (012)
# ---------------------------------------------------------------------------

class TestAddImageScript:
    def test_basic_script_structure(self):
        script = scripts.add_image(slide=1, path="/tmp/test.png", x=600, y=120, width=620, height=430)
        assert 'tell slide 1' in script
        assert 'make new image with properties {file:POSIX file "/tmp/test.png"}' in script
        assert 'set position of imageItem to {600, 120}' in script
        assert 'set width of imageItem to 620' in script
        assert 'set height of imageItem to 430' in script
        assert 'return count of images' in script

    def test_does_not_write_object_name(self):
        # object_id is local-only; Keynote image items don't reliably support writable object name
        script = scripts.add_image(slide=1, path="/tmp/img.png", x=0, y=0, width=100, height=100)
        assert 'object name' not in script

    def test_escapes_path_with_quotes(self):
        script = scripts.add_image(slide=1, path='/tmp/my "deck".png', x=0, y=0, width=100, height=100)
        assert '\\"' in script
        assert 'my "deck"' not in script

    def test_float_geometry_formatted(self):
        script = scripts.add_image(slide=1, path="/tmp/img.png", x=100.5, y=200.5, width=300.5, height=400.5)
        assert '100.5' in script
        assert '200.5' in script


# ---------------------------------------------------------------------------
# keynote.add_image handler (012)
# ---------------------------------------------------------------------------

class TestAddImageTool:
    def _make_png(self, tmp_path: Path, name: str = "slide_01.png") -> Path:
        p = tmp_path / name
        p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8)  # minimal fake PNG header
        return p

    def test_registers_image_in_context(self, tmp_path: Path):
        png = self._make_png(tmp_path)
        fake = FakeScriptRunner()
        result, state = _run_tool(
            "keynote.add_image",
            {"slide": 1, "path": str(png), "x": 600, "y": 120, "width": 620, "height": 430, "object_id": "slide_01_art"},
            fake,
        )
        assert result.ok
        obj = state.context["keynote"]["objects"]["slide_01_art"]
        assert obj["type"] == "image"
        assert obj["slide"] == 1
        assert obj["x"] == 600.0
        assert obj["y"] == 120.0
        assert obj["width"] == 620.0
        assert obj["height"] == 430.0
        assert obj["apple_class"] == "image"
        assert obj["apple_index"] == 1

    def test_context_type_is_image(self, tmp_path: Path):
        png = self._make_png(tmp_path)
        _, state = _run_tool(
            "keynote.add_image",
            {"slide": 1, "path": str(png), "x": 0, "y": 0, "width": 100, "height": 100, "object_id": "slide_01_art"},
            FakeScriptRunner(),
        )
        assert state.context["keynote"]["objects"]["slide_01_art"]["type"] == "image"

    def test_slide_objects_index_updated(self, tmp_path: Path):
        png = self._make_png(tmp_path)
        _, state = _run_tool(
            "keynote.add_image",
            {"slide": 1, "path": str(png), "x": 0, "y": 0, "width": 100, "height": 100, "object_id": "slide_01_art"},
            FakeScriptRunner(),
        )
        assert "slide_01_art" in state.context["keynote"]["slides"]["1"]["objects"]

    def test_missing_file_raises(self, tmp_path: Path):
        fake = FakeScriptRunner()
        result, _ = _run_tool(
            "keynote.add_image",
            {"slide": 1, "path": str(tmp_path / "nonexistent.png"), "x": 0, "y": 0, "width": 100, "height": 100},
            fake,
        )
        assert result.ok is False
        assert "not a file" in (result.error or "").lower() or "does not exist" in (result.error or "").lower()

    def test_invalid_slide_raises(self, tmp_path: Path):
        png = self._make_png(tmp_path)
        result, _ = _run_tool(
            "keynote.add_image",
            {"slide": 0, "path": str(png), "x": 0, "y": 0, "width": 100, "height": 100},
            FakeScriptRunner(),
        )
        assert result.ok is False

    def test_invalid_geometry_negative_width(self, tmp_path: Path):
        png = self._make_png(tmp_path)
        result, _ = _run_tool(
            "keynote.add_image",
            {"slide": 1, "path": str(png), "x": 0, "y": 0, "width": -1, "height": 100},
            FakeScriptRunner(),
        )
        assert result.ok is False

    def test_invalid_object_id_raises(self, tmp_path: Path):
        png = self._make_png(tmp_path)
        result, _ = _run_tool(
            "keynote.add_image",
            {"slide": 1, "path": str(png), "x": 0, "y": 0, "width": 100, "height": 100, "object_id": "INVALID ID!"},
            FakeScriptRunner(),
        )
        assert result.ok is False

    def test_auto_object_id_generated(self, tmp_path: Path):
        png = self._make_png(tmp_path)
        result, state = _run_tool(
            "keynote.add_image",
            {"slide": 1, "path": str(png), "x": 0, "y": 0, "width": 100, "height": 100},
            FakeScriptRunner(),
        )
        assert result.ok
        oid = result.output["object_id"]
        assert oid.startswith("slide_01_image")
        assert oid in state.context["keynote"]["objects"]

    def test_path_stored_as_absolute(self, tmp_path: Path):
        png = self._make_png(tmp_path)
        _, state = _run_tool(
            "keynote.add_image",
            {"slide": 1, "path": str(png), "x": 0, "y": 0, "width": 100, "height": 100, "object_id": "slide_01_art"},
            FakeScriptRunner(),
        )
        stored_path = state.context["keynote"]["objects"]["slide_01_art"]["path"]
        assert Path(stored_path).is_absolute()
