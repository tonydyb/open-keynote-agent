"""Tests for the storybook renderer (change 009).

No Keynote, osascript, GUI access, or macOS Automation permissions required.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

import open_keynote_agent.cli as cli_module
from open_keynote_agent.agent.registry import ToolRegistry
from open_keynote_agent.agent.session import SessionState
from open_keynote_agent.applescript import scripts
from open_keynote_agent.applescript.runner import FakeScriptRunner, ScriptRunResult
from open_keynote_agent.cli import app
from open_keynote_agent.deck.schema import DeckSpec, SlideSpec, StyleSpec, VisualSpec
from open_keynote_agent.renderers.storybook import RenderResult, render_storybook_deck
from open_keynote_agent.renderers.templates import (
    FALLBACK_EMOJI,
    FALLBACK_EMOJI_DEFAULT,
    LAYOUT_FOR_KIND,
    calls_for_slide,
)
from open_keynote_agent.tools.keynote import register_keynote_tools

cli_runner = CliRunner()


# ---------------------------------------------------------------------------
# Test fixtures and helpers
# ---------------------------------------------------------------------------

def _visual(**kw) -> VisualSpec:
    base: dict[str, Any] = {"description": "a scene"}
    base.update(kw)
    return VisualSpec(**base)


def _slide(index: int, kind: str = "content", title: str = "Slide", **kw) -> SlideSpec:
    base: dict[str, Any] = {"index": index, "kind": kind, "title": title, "visual": _visual()}
    base.update(kw)
    return SlideSpec(**base)


def _three_pigs_deck() -> DeckSpec:
    """Minimal Three Little Pigs DeckSpec (8 slides, cover first)."""
    slides = [
        SlideSpec(index=1, kind="cover", title="三只小猪与大灰狼",
                  visual=VisualSpec(description="cover", emoji=["🐷", "🐺"])),
        SlideSpec(index=2, kind="characters", title="角色介绍",
                  body=["大毛", "二毛", "小毛"],
                  visual=VisualSpec(description="characters", emoji=["🐷", "🐷", "🐷"])),
        SlideSpec(index=3, kind="chapter", title="第一章",
                  body=["大毛的稻草屋"],
                  visual=VisualSpec(description="straw house", emoji=["🌾"])),
        SlideSpec(index=4, kind="chapter", title="第二章",
                  body=["二毛的木屋"],
                  visual=VisualSpec(description="wooden house", emoji=["🪵"])),
        SlideSpec(index=5, kind="chapter", title="第三章",
                  body=["小毛的砖房"],
                  visual=VisualSpec(description="brick house", emoji=["🧱"])),
        SlideSpec(index=6, kind="climax", title="大灰狼来了",
                  body=["大灰狼吹"],
                  visual=VisualSpec(description="wolf blowing", emoji=["🐺", "💨"])),
        SlideSpec(index=7, kind="lesson", title="勤劳的力量",
                  body=["努力才能保护我们"],
                  visual=VisualSpec(description="lesson", emoji=["✨"])),
        SlideSpec(index=8, kind="ending", title="The End",
                  visual=VisualSpec(description="ending", emoji=["🌸"])),
    ]
    return DeckSpec(
        title="三只小猪与大灰狼",
        style=StyleSpec(mood="warm storybook"),
        theme="Parchment",
        slides=slides,
    )


def _make_fake_runner(themes: str = "Parchment\nBasic White\n") -> FakeScriptRunner:
    """Build a FakeScriptRunner pre-loaded with happy-path responses."""
    fake = FakeScriptRunner()
    fake.responses[scripts.list_themes()] = ScriptRunResult(
        stdout=themes, stderr="", returncode=0
    )
    fake.responses[scripts.list_layouts()] = ScriptRunResult(
        stdout="Title\nTitle & Bullets\nBlank\n", stderr="", returncode=0
    )
    # add_slide, set_slide_title, add_text_box, add_emoji_text, add_shape, export_pdf
    # all default to stdout="1", ok=True via FakeScriptRunner default
    return fake


def _make_registry_and_state(fake: FakeScriptRunner) -> tuple[ToolRegistry, SessionState]:
    registry = ToolRegistry()
    register_keynote_tools(registry, fake)
    return registry, SessionState()


def _render_three_pigs(tmp_path: Path, fake: FakeScriptRunner | None = None) -> RenderResult:
    if fake is None:
        fake = _make_fake_runner()
    registry, state = _make_registry_and_state(fake)
    deck = _three_pigs_deck()
    return render_storybook_deck(deck, registry, state, output_dir=tmp_path, export_pdf=False)


# ---------------------------------------------------------------------------
# Template system tests
# ---------------------------------------------------------------------------

class TestLayoutForKind:
    def test_cover_maps_to_title(self):
        assert LAYOUT_FOR_KIND["cover"] == "title"

    def test_characters_maps_to_title_body(self):
        assert LAYOUT_FOR_KIND["characters"] == "title_body"

    def test_chapter_maps_to_title_body(self):
        assert LAYOUT_FOR_KIND["chapter"] == "title_body"

    def test_climax_maps_to_title_body(self):
        assert LAYOUT_FOR_KIND["climax"] == "title_body"

    def test_lesson_maps_to_title_body(self):
        assert LAYOUT_FOR_KIND["lesson"] == "title_body"

    def test_ending_maps_to_title(self):
        assert LAYOUT_FOR_KIND["ending"] == "title"

    def test_content_maps_to_title_body(self):
        assert LAYOUT_FOR_KIND["content"] == "title_body"


class TestFallbackEmoji:
    def test_cover_fallback(self):
        slide = _slide(1, kind="cover")
        calls = calls_for_slide(slide)
        emoji_calls = [c for c in calls if c.tool == "keynote.add_emoji_text"]
        assert len(emoji_calls) >= 1
        assert emoji_calls[0].args["emoji"] == FALLBACK_EMOJI["cover"]

    def test_climax_fallback(self):
        slide = _slide(1, kind="climax")
        calls = calls_for_slide(slide)
        emoji_calls = [c for c in calls if c.tool == "keynote.add_emoji_text"]
        assert emoji_calls[0].args["emoji"] == FALLBACK_EMOJI["climax"]

    def test_ending_fallback(self):
        slide = _slide(1, kind="ending")
        calls = calls_for_slide(slide)
        emoji_calls = [c for c in calls if c.tool == "keynote.add_emoji_text"]
        assert emoji_calls[0].args["emoji"] == FALLBACK_EMOJI["ending"]

    def test_default_fallback_for_content(self):
        slide = _slide(1, kind="content")
        calls = calls_for_slide(slide)
        emoji_calls = [c for c in calls if c.tool == "keynote.add_emoji_text"]
        assert emoji_calls[0].args["emoji"] == FALLBACK_EMOJI_DEFAULT

    def test_provided_emoji_used_when_present(self):
        slide = _slide(1, kind="cover", visual=_visual(emoji=["🐷", "🐺"]))
        calls = calls_for_slide(slide)
        emoji_calls = [c for c in calls if c.tool == "keynote.add_emoji_text"]
        emojis = [c.args["emoji"] for c in emoji_calls]
        assert "🐷" in emojis
        assert "🐺" in emojis


class TestTemplateShapeConstraints:
    def test_cover_panel_is_rectangle(self):
        slide = _slide(1, kind="cover")
        calls = calls_for_slide(slide)
        shape_calls = [c for c in calls if c.tool == "keynote.add_shape"]
        for sc in shape_calls:
            assert sc.args["shape"] == "rectangle"

    def test_no_fill_color_in_any_template(self):
        for kind in LAYOUT_FOR_KIND:
            slide = _slide(3, kind=kind)
            calls = calls_for_slide(slide)
            for call in calls:
                if call.tool == "keynote.add_shape":
                    assert "fill_color" not in call.args, f"fill_color found in {kind} template"

    def test_no_unsupported_shape_kinds(self):
        supported = {"rectangle"}
        for kind in LAYOUT_FOR_KIND:
            slide = _slide(2, kind=kind)
            calls = calls_for_slide(slide)
            for call in calls:
                if call.tool == "keynote.add_shape":
                    assert call.args["shape"] in supported


class TestDeterministicObjectIds:
    def test_cover_subtitle_id(self):
        slide = SlideSpec(
            index=1, kind="cover", title="T", subtitle="S",
            visual=VisualSpec(description="x"),
        )
        calls = calls_for_slide(slide)
        ids = [c.args.get("object_id") for c in calls if "object_id" in c.args]
        assert "slide_01_subtitle" in ids

    def test_cover_panel_id(self):
        slide = _slide(1, kind="cover")
        calls = calls_for_slide(slide)
        ids = [c.args.get("object_id") for c in calls if "object_id" in c.args]
        assert "slide_01_panel" in ids

    def test_emoji_ids_sequential(self):
        slide = _slide(3, kind="chapter", visual=_visual(emoji=["🐷", "🐺", "⭐"]))
        calls = calls_for_slide(slide)
        emoji_ids = [c.args["object_id"] for c in calls if c.tool == "keynote.add_emoji_text"]
        assert emoji_ids == ["slide_03_emoji_1", "slide_03_emoji_2", "slide_03_emoji_3"]

    def test_body_id(self):
        slide = _slide(5, kind="chapter", body=["bullet"])
        calls = calls_for_slide(slide)
        ids = [c.args.get("object_id") for c in calls if "object_id" in c.args]
        assert "slide_05_body" in ids


class TestChapterAlternation:
    def test_even_index_body_on_left(self):
        slide = _slide(4, kind="chapter", body=["text"])
        calls = calls_for_slide(slide)
        body_calls = [c for c in calls if c.tool == "keynote.add_text_box"]
        assert len(body_calls) == 1
        # even index (4): body on left (x < 640)
        assert body_calls[0].args["x"] < 640

    def test_odd_index_body_on_right(self):
        slide = _slide(3, kind="chapter", body=["text"])
        calls = calls_for_slide(slide)
        body_calls = [c for c in calls if c.tool == "keynote.add_text_box"]
        assert len(body_calls) == 1
        # odd index (3): body on right (x >= 640)
        assert body_calls[0].args["x"] >= 640


class TestMaxFourEmoji:
    def test_at_most_four_emoji_calls(self):
        slide = _slide(1, kind="cover",
                       visual=_visual(emoji=["🐷", "🐺", "⭐", "🌸", "📖"]))
        calls = calls_for_slide(slide)
        emoji_calls = [c for c in calls if c.tool == "keynote.add_emoji_text"]
        assert len(emoji_calls) <= 4


# ---------------------------------------------------------------------------
# Renderer execution tests
# ---------------------------------------------------------------------------

class TestThemeSelection:
    def _render_themes(self, themes_stdout: str, deck_theme: str | None) -> str:
        fake = FakeScriptRunner()
        fake.responses[scripts.list_themes()] = ScriptRunResult(
            stdout=themes_stdout, stderr="", returncode=0
        )
        fake.responses[scripts.list_layouts()] = ScriptRunResult(
            stdout="Title\nTitle & Bullets\nBlank\n", stderr="", returncode=0
        )
        deck = _three_pigs_deck()
        deck = deck.model_copy(update={"theme": deck_theme})
        registry, state = _make_registry_and_state(fake)
        result = render_storybook_deck(deck, registry, state, output_dir=Path("/tmp"), export_pdf=False)
        return result.theme

    def test_uses_deck_theme_when_available(self):
        theme = self._render_themes("Parchment\nBasic White\n", deck_theme="Parchment")
        assert theme == "Parchment"

    def test_falls_back_to_parchment_when_deck_theme_absent(self):
        theme = self._render_themes("Parchment\nBasic White\n", deck_theme=None)
        assert theme == "Parchment"

    def test_falls_back_to_basic_white(self):
        theme = self._render_themes("Basic White\nCraft\n", deck_theme=None)
        assert theme == "Basic White"

    def test_falls_back_to_first_available(self):
        theme = self._render_themes("Craft\nMinimalist\n", deck_theme=None)
        assert theme == "Craft"

    def test_prefers_deck_theme_over_parchment(self):
        theme = self._render_themes("Parchment\nCraft\n", deck_theme="Craft")
        assert theme == "Craft"

    def test_deck_theme_unavailable_falls_back_to_parchment(self):
        theme = self._render_themes("Parchment\nBasic White\n", deck_theme="NonExistent")
        assert theme == "Parchment"


class TestSlideCountAndAddSlide:
    def test_one_keynote_slide_per_deck_spec_slide(self, tmp_path: Path):
        result = _render_three_pigs(tmp_path)
        assert result.slide_count == 8

    def test_add_slide_not_called_for_first_slide(self, tmp_path: Path):
        fake = _make_fake_runner()
        _render_three_pigs(tmp_path, fake)
        add_slide_calls = [c for c in fake.calls if "make new slide" in c]
        # First slide is the default; add_slide only called for slides 2..N
        assert len(add_slide_calls) == 7  # 8 slides - 1 default = 7 add_slide calls

    def test_add_slide_called_for_slides_2_through_n(self, tmp_path: Path):
        fake = _make_fake_runner()
        _render_three_pigs(tmp_path, fake)
        add_slide_calls = [c for c in fake.calls if "make new slide" in c]
        assert len(add_slide_calls) == 7

    def test_set_title_called_for_every_slide(self, tmp_path: Path):
        fake = _make_fake_runner()
        _render_three_pigs(tmp_path, fake)
        set_title_calls = [c for c in fake.calls if "default title item" in c]
        assert len(set_title_calls) == 8


class TestFirstSlideMustBeCover:
    def test_non_cover_first_slide_raises_before_any_tool_call(self):
        slides = [
            SlideSpec(index=1, kind="chapter", title="Not a cover",
                      visual=VisualSpec(description="x")),
            SlideSpec(index=2, kind="ending", title="End",
                      visual=VisualSpec(description="x")),
        ]
        deck = DeckSpec(
            title="Bad Deck",
            style=StyleSpec(mood="x"),
            slides=slides,
        )
        fake = _make_fake_runner()
        registry, state = _make_registry_and_state(fake)
        with pytest.raises(ValueError, match="cover"):
            render_storybook_deck(deck, registry, state, output_dir=Path("/tmp"), export_pdf=False)
        # No Keynote tools should have been called
        assert fake.calls == []


class TestRenderStopsOnFailure:
    def test_stops_on_list_themes_failure(self, tmp_path: Path):
        fake = FakeScriptRunner()
        fake.responses[scripts.list_themes()] = ScriptRunResult(stdout="", stderr="no Keynote", returncode=1)
        registry, state = _make_registry_and_state(fake)
        with pytest.raises(RuntimeError, match="keynote.list_themes"):
            render_storybook_deck(_three_pigs_deck(), registry, state, output_dir=tmp_path, export_pdf=False)

    def test_stops_on_create_document_failure(self, tmp_path: Path):
        fake = FakeScriptRunner()
        fake.responses[scripts.list_themes()] = ScriptRunResult(
            stdout="Parchment\n", stderr="", returncode=0
        )
        create_script = scripts.create_document("三只小猪与大灰狼", theme="Parchment")
        fake.responses[create_script] = ScriptRunResult(stdout="", stderr="create failed", returncode=1)
        registry, state = _make_registry_and_state(fake)
        with pytest.raises(RuntimeError, match="keynote.create_document"):
            render_storybook_deck(_three_pigs_deck(), registry, state, output_dir=tmp_path, export_pdf=False)


class TestToolResultsPopulated:
    def test_tool_results_is_non_empty(self, tmp_path: Path):
        result = _render_three_pigs(tmp_path)
        assert len(result.tool_results) > 0

    def test_tool_results_contain_list_themes(self, tmp_path: Path):
        result = _render_three_pigs(tmp_path)
        tools = [r["tool"] for r in result.tool_results]
        assert "keynote.list_themes" in tools

    def test_tool_results_contain_create_document(self, tmp_path: Path):
        result = _render_three_pigs(tmp_path)
        tools = [r["tool"] for r in result.tool_results]
        assert "keynote.create_document" in tools

    def test_tool_results_contain_set_slide_title(self, tmp_path: Path):
        result = _render_three_pigs(tmp_path)
        tools = [r["tool"] for r in result.tool_results]
        assert "keynote.set_slide_title" in tools

    def test_all_tool_results_have_ok_field(self, tmp_path: Path):
        result = _render_three_pigs(tmp_path)
        for record in result.tool_results:
            assert "ok" in record


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class TestRenderStorybookCLI:
    def _write_deck_spec(self, tmp_path: Path, deck: DeckSpec | None = None) -> Path:
        if deck is None:
            deck = _three_pigs_deck()
        p = tmp_path / "deck_spec.json"
        p.write_text(deck.model_dump_json(), encoding="utf-8")
        return p

    def _fake_register(self, fake: FakeScriptRunner):
        def patched(registry, runner):
            return register_keynote_tools(registry, fake)
        return patched

    def test_writes_render_result_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = _make_fake_runner()
        monkeypatch.setattr(cli_module, "register_keynote_tools", self._fake_register(fake))
        spec_path = self._write_deck_spec(tmp_path)
        out = tmp_path / "out"
        result = cli_runner.invoke(app, ["render-storybook", str(spec_path), "--output", str(out), "--no-pdf"])
        assert result.exit_code == 0, result.output
        assert (out / "render_result.json").exists()

    def test_writes_tool_results_jsonl(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = _make_fake_runner()
        monkeypatch.setattr(cli_module, "register_keynote_tools", self._fake_register(fake))
        spec_path = self._write_deck_spec(tmp_path)
        out = tmp_path / "out"
        cli_runner.invoke(app, ["render-storybook", str(spec_path), "--output", str(out), "--no-pdf"])
        assert (out / "tool_results.jsonl").exists()
        lines = (out / "tool_results.jsonl").read_text().splitlines()
        assert len(lines) > 0
        record = json.loads(lines[0])
        assert "tool" in record
        assert "ok" in record

    def test_tool_results_jsonl_from_render_result(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = _make_fake_runner()
        monkeypatch.setattr(cli_module, "register_keynote_tools", self._fake_register(fake))
        spec_path = self._write_deck_spec(tmp_path)
        out = tmp_path / "out"
        cli_runner.invoke(app, ["render-storybook", str(spec_path), "--output", str(out), "--no-pdf"])
        lines = (out / "tool_results.jsonl").read_text().splitlines()
        tools = [json.loads(line)["tool"] for line in lines]
        assert "keynote.list_themes" in tools

    def test_render_result_json_contains_slide_count(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = _make_fake_runner()
        monkeypatch.setattr(cli_module, "register_keynote_tools", self._fake_register(fake))
        spec_path = self._write_deck_spec(tmp_path)
        out = tmp_path / "out"
        cli_runner.invoke(app, ["render-storybook", str(spec_path), "--output", str(out), "--no-pdf"])
        data = json.loads((out / "render_result.json").read_text())
        assert data["slide_count"] == 8

    def test_invalid_deck_spec_exits_nonzero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        bad = tmp_path / "bad.json"
        bad.write_text('{"not": "a deck spec"}')
        result = cli_runner.invoke(app, ["render-storybook", str(bad), "--output", str(tmp_path / "out")])
        assert result.exit_code != 0

    def test_missing_input_file_exits_nonzero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        result = cli_runner.invoke(app, ["render-storybook", str(tmp_path / "nope.json")])
        assert result.exit_code != 0

    def test_refuses_to_overwrite_render_result(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = _make_fake_runner()
        monkeypatch.setattr(cli_module, "register_keynote_tools", self._fake_register(fake))
        spec_path = self._write_deck_spec(tmp_path)
        out = tmp_path / "out"
        out.mkdir()
        (out / "render_result.json").write_text("{}")
        result = cli_runner.invoke(app, ["render-storybook", str(spec_path), "--output", str(out), "--no-pdf"])
        assert result.exit_code != 0

    def test_refuses_to_overwrite_tool_results_jsonl(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = _make_fake_runner()
        monkeypatch.setattr(cli_module, "register_keynote_tools", self._fake_register(fake))
        spec_path = self._write_deck_spec(tmp_path)
        out = tmp_path / "out"
        out.mkdir()
        (out / "tool_results.jsonl").write_text("")
        result = cli_runner.invoke(app, ["render-storybook", str(spec_path), "--output", str(out), "--no-pdf"])
        assert result.exit_code != 0

    def test_default_output_dir_under_runs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = _make_fake_runner()
        monkeypatch.setattr(cli_module, "register_keynote_tools", self._fake_register(fake))
        spec_path = self._write_deck_spec(tmp_path)
        result = cli_runner.invoke(app, ["render-storybook", str(spec_path), "--no-pdf"])
        assert result.exit_code == 0, result.output
        runs = list((tmp_path / ".runs").iterdir())
        assert len(runs) == 1
        assert "storybook" in runs[0].name
        assert (runs[0] / "render_result.json").exists()

    def test_prints_automation_warning(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = _make_fake_runner()
        monkeypatch.setattr(cli_module, "register_keynote_tools", self._fake_register(fake))
        spec_path = self._write_deck_spec(tmp_path)
        out = tmp_path / "out"
        result = cli_runner.invoke(app, ["render-storybook", str(spec_path), "--output", str(out), "--no-pdf"])
        assert "Automation" in result.output

    def test_does_not_call_llm(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = _make_fake_runner()
        monkeypatch.setattr(cli_module, "register_keynote_tools", self._fake_register(fake))
        # Ensure load_llm_client_from_env is never called
        called = []
        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: called.append(1) or MagicMock())
        spec_path = self._write_deck_spec(tmp_path)
        out = tmp_path / "out"
        cli_runner.invoke(app, ["render-storybook", str(spec_path), "--output", str(out), "--no-pdf"])
        assert called == []

    def test_no_pdf_skips_export(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = _make_fake_runner()
        monkeypatch.setattr(cli_module, "register_keynote_tools", self._fake_register(fake))
        spec_path = self._write_deck_spec(tmp_path)
        out = tmp_path / "out"
        cli_runner.invoke(app, ["render-storybook", str(spec_path), "--output", str(out), "--no-pdf"])
        export_pdf_calls = [c for c in fake.calls if "export" in c.lower()]
        assert export_pdf_calls == []

    def test_default_dir_cleaned_on_invalid_deck(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        bad = tmp_path / "bad.json"
        bad.write_text('{"not": "a spec"}')
        result = cli_runner.invoke(app, ["render-storybook", str(bad)])
        assert result.exit_code != 0
        runs = tmp_path / ".runs"
        if runs.exists():
            leftover = list(runs.iterdir())
            assert leftover == [], f"Unexpected dirs: {leftover}"


# ---------------------------------------------------------------------------
# Integration smoke test (opt-in)
# ---------------------------------------------------------------------------

keynote_integration = pytest.mark.skipif(
    os.environ.get("RUN_KEYNOTE_INTEGRATION") != "1",
    reason="Set RUN_KEYNOTE_INTEGRATION=1 to run real Keynote integration tests",
)


@keynote_integration
@pytest.mark.keynote_integration
def test_storybook_smoke(tmp_path: Path):
    """Render Three Little Pigs with real Keynote and verify PDF output."""
    from open_keynote_agent.applescript.runner import OsascriptRunner

    registry = ToolRegistry()
    register_keynote_tools(registry, OsascriptRunner())
    state = SessionState()
    deck = _three_pigs_deck()

    result = render_storybook_deck(deck, registry, state, output_dir=tmp_path, export_pdf=True)

    assert result.slide_count == 8
    assert result.pdf_path is not None
    pdf = Path(result.pdf_path)
    assert pdf.exists()
    assert pdf.stat().st_size > 0
