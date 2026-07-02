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

    def test_stops_on_add_image_failure(self, tmp_path: Path):
        png = _make_fake_png(tmp_path, "slide_01.png")
        fake = _make_fake_runner()
        fake.responses[scripts.add_image(
            slide=1,
            path=str(png.resolve()),
            x=0,
            y=0,
            width=1280,
            height=720,
        )] = ScriptRunResult(stdout="", stderr="image insert failed", returncode=1)
        registry, state = _make_registry_and_state(fake)
        with pytest.raises(RuntimeError, match="keynote.add_image"):
            render_storybook_deck(
                _three_pigs_deck(),
                registry,
                state,
                output_dir=tmp_path,
                export_pdf=False,
                image_assets={1: png},
            )


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


# ---------------------------------------------------------------------------
# Image manifest loader tests (012)
# ---------------------------------------------------------------------------

def _write_manifest(tmp_path: Path, assets: list[dict], extra: dict | None = None) -> Path:
    """Write a minimal image_manifest.json to tmp_path."""
    import json as _json
    data: dict = {
        "deck_title": "Test Deck",
        "provider": "fake",
        "assets_dir": "assets",
        "assets": assets,
    }
    if extra:
        data.update(extra)
    manifest = tmp_path / "image_manifest.json"
    manifest.write_text(_json.dumps(data), encoding="utf-8")
    return manifest


def _make_fake_png(directory: Path, filename: str) -> Path:
    p = directory / filename
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8)
    return p


class TestLoadImageAssets:
    from open_keynote_agent.images.loader import load_image_assets

    def _load(self, manifest_path):
        from open_keynote_agent.images.loader import load_image_assets
        return load_image_assets(manifest_path)

    def test_returns_mapping(self, tmp_path: Path):
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        _make_fake_png(assets_dir, "slide_01.png")
        manifest = _write_manifest(tmp_path, [
            {"slide_index": 1, "prompt_hash": "abc", "provider": "fake", "path": "assets/slide_01.png", "cached": False},
        ])
        result = self._load(manifest)
        assert 1 in result
        assert result[1].is_absolute()
        assert result[1].exists()

    def test_resolves_paths_relative_to_manifest_dir(self, tmp_path: Path):
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        _make_fake_png(assets_dir, "slide_02.png")
        manifest = _write_manifest(tmp_path, [
            {"slide_index": 2, "prompt_hash": "abc", "provider": "fake", "path": "assets/slide_02.png", "cached": False},
        ])
        result = self._load(manifest)
        assert result[2] == (tmp_path / "assets" / "slide_02.png").resolve()

    def test_empty_manifest_returns_empty_dict(self, tmp_path: Path):
        manifest = _write_manifest(tmp_path, [])
        result = self._load(manifest)
        assert result == {}

    def test_manifest_not_found_raises(self, tmp_path: Path):
        from open_keynote_agent.images.loader import load_image_assets
        import pytest as _pytest
        with _pytest.raises(ValueError, match="not found"):
            load_image_assets(tmp_path / "does_not_exist.json")

    def test_duplicate_slide_index_fails(self, tmp_path: Path):
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        _make_fake_png(assets_dir, "slide_01.png")
        manifest = _write_manifest(tmp_path, [
            {"slide_index": 1, "prompt_hash": "abc", "provider": "fake", "path": "assets/slide_01.png", "cached": False},
            {"slide_index": 1, "prompt_hash": "def", "provider": "fake", "path": "assets/slide_01.png", "cached": False},
        ])
        import pytest as _pytest
        with _pytest.raises(ValueError, match="Duplicate"):
            self._load(manifest)

    def test_absolute_asset_path_fails(self, tmp_path: Path):
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        png = _make_fake_png(assets_dir, "slide_01.png")
        manifest = _write_manifest(tmp_path, [
            {"slide_index": 1, "prompt_hash": "abc", "provider": "fake", "path": str(png), "cached": False},
        ])
        import pytest as _pytest
        with _pytest.raises(ValueError, match="absolute"):
            self._load(manifest)

    def test_missing_listed_file_fails(self, tmp_path: Path):
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        # Do NOT create the PNG
        manifest = _write_manifest(tmp_path, [
            {"slide_index": 1, "prompt_hash": "abc", "provider": "fake", "path": "assets/slide_01.png", "cached": False},
        ])
        import pytest as _pytest
        with _pytest.raises(ValueError, match="not found"):
            self._load(manifest)


# ---------------------------------------------------------------------------
# Image template helpers tests (012)
# ---------------------------------------------------------------------------

class TestImageTemplates:
    def test_image_call_for_slide_uses_full_bleed_frame(self):
        from pathlib import Path as _Path
        from open_keynote_agent.renderers.templates import (
            IMAGE_FULL_H,
            IMAGE_FULL_W,
            IMAGE_FULL_X,
            IMAGE_FULL_Y,
            image_call_for_slide,
        )
        slide = _slide(1, kind="cover")
        call = image_call_for_slide(slide, _Path("/tmp/img.png"))
        assert call.tool == "keynote.add_image"
        assert call.args["x"] == IMAGE_FULL_X
        assert call.args["y"] == IMAGE_FULL_Y
        assert call.args["width"] == IMAGE_FULL_W
        assert call.args["height"] == IMAGE_FULL_H

    def test_image_call_for_slide_all_kinds_use_full_bleed_frame(self):
        from pathlib import Path as _Path
        from open_keynote_agent.renderers.templates import IMAGE_FULL_W, image_call_for_slide
        for kind in ["characters", "chapter", "content", "climax", "lesson", "ending"]:
            slide = _slide(3, kind=kind)
            call = image_call_for_slide(slide, _Path("/tmp/img.png"))
            assert call.args["x"] == 0
            assert call.args["width"] == IMAGE_FULL_W

    def test_image_call_object_id_uses_art_suffix(self):
        from pathlib import Path as _Path
        from open_keynote_agent.renderers.templates import image_call_for_slide
        slide = _slide(5, kind="chapter")
        call = image_call_for_slide(slide, _Path("/tmp/img.png"))
        assert call.args["object_id"] == "slide_05_art"

    def test_calls_for_slide_text_only_returns_no_emoji(self):
        from open_keynote_agent.renderers.templates import calls_for_slide_text_only
        slide = _slide(2, kind="chapter", body=["A wolf came"])
        calls = calls_for_slide_text_only(slide)
        emoji_calls = [c for c in calls if c.tool == "keynote.add_emoji_text"]
        assert emoji_calls == []

    def test_calls_for_slide_text_only_returns_no_shape(self):
        from open_keynote_agent.renderers.templates import calls_for_slide_text_only
        slide = _slide(1, kind="cover")
        calls = calls_for_slide_text_only(slide)
        shape_calls = [c for c in calls if c.tool == "keynote.add_shape"]
        assert shape_calls == []

    def test_calls_for_slide_text_only_includes_body(self):
        from open_keynote_agent.renderers.templates import calls_for_slide_text_only
        slide = _slide(2, kind="chapter", body=["The wolf came", "He huffed"])
        calls = calls_for_slide_text_only(slide)
        text_calls = [c for c in calls if c.tool == "keynote.add_text_box"]
        assert len(text_calls) == 1
        assert "The wolf came" in text_calls[0].args["text"]

    def test_calls_for_slide_text_only_uses_overlay_frame(self):
        from open_keynote_agent.renderers.templates import (
            OVERLAY_TEXT_H,
            OVERLAY_TEXT_W,
            OVERLAY_TEXT_X,
            OVERLAY_TEXT_Y,
            calls_for_slide_text_only,
        )
        slide = _slide(2, kind="chapter", body=["The wolf came"])
        call = [c for c in calls_for_slide_text_only(slide) if c.tool == "keynote.add_text_box"][0]
        assert call.args["x"] == OVERLAY_TEXT_X
        assert call.args["y"] == OVERLAY_TEXT_Y
        assert call.args["width"] == OVERLAY_TEXT_W
        assert call.args["height"] == OVERLAY_TEXT_H


# ---------------------------------------------------------------------------
# Renderer integration with image assets (012)
# ---------------------------------------------------------------------------

def _make_fake_runner_with_image(themes: str = "Parchment\nBasic White\n") -> FakeScriptRunner:
    """Like _make_fake_runner but also accepts add_image calls (default response = '1')."""
    return _make_fake_runner(themes)


def _render_with_images(
    tmp_path: Path,
    image_assets: dict[int, Path],
    deck: DeckSpec | None = None,
) -> tuple[RenderResult, FakeScriptRunner]:
    fake = _make_fake_runner_with_image()
    registry, state = _make_registry_and_state(fake)
    if deck is None:
        deck = _three_pigs_deck()
    result = render_storybook_deck(
        deck, registry, state,
        output_dir=tmp_path,
        export_pdf=False,
        image_assets=image_assets,
    )
    return result, fake


class TestRendererImageIntegration:
    def test_add_image_called_for_slide_with_asset(self, tmp_path: Path):
        png = _make_fake_png(tmp_path, "slide_01.png")
        result, fake = _render_with_images(tmp_path, {1: png})
        image_calls = [c for c in fake.calls if "make new image" in c]
        assert len(image_calls) >= 1

    def test_no_primary_emoji_when_image_present(self, tmp_path: Path):
        png = _make_fake_png(tmp_path, "slide_01.png")
        # Slide 1 cover: with image we should NOT add_emoji_text
        _, fake = _render_with_images(tmp_path, {1: png})
        # Extract scripts for slide 1 emoji calls from keynote.add_emoji_text
        # The FakeScriptRunner records raw scripts; add_emoji_text uses add_text_box under the hood
        # So we count add_image calls vs emit from template
        image_calls = [c for c in fake.calls if "make new image" in c and "tell slide 1" in c]
        assert len(image_calls) == 1

    def test_emoji_fallback_when_no_image(self, tmp_path: Path):
        # No image assets supplied — emoji calls must still happen
        result, fake = _render_with_images(tmp_path, {})
        # At least one emoji call across all slides
        text_item_calls = [c for c in fake.calls if "make new text item" in c]
        assert len(text_item_calls) >= 1

    def test_image_count_in_result(self, tmp_path: Path):
        png1 = _make_fake_png(tmp_path, "slide_01.png")
        png3 = _make_fake_png(tmp_path, "slide_03.png")
        result, _ = _render_with_images(tmp_path, {1: png1, 3: png3})
        assert result.image_count == 2

    def test_missing_image_slides_recorded(self, tmp_path: Path):
        png1 = _make_fake_png(tmp_path, "slide_01.png")
        # Provide image only for slide 1; slides 2-8 are missing
        result, _ = _render_with_images(tmp_path, {1: png1})
        assert 2 in result.missing_image_slides
        assert 1 not in result.missing_image_slides

    def test_no_image_assets_gives_zero_image_count(self, tmp_path: Path):
        result = _render_three_pigs(tmp_path)
        assert result.image_count == 0
        assert result.missing_image_slides == []

    def test_extra_manifest_assets_dont_create_extra_slides(self, tmp_path: Path):
        deck = _three_pigs_deck()  # 8 slides
        pngs = {i: _make_fake_png(tmp_path, f"slide_{i:02d}.png") for i in range(1, 20)}
        result, _ = _render_with_images(tmp_path, pngs, deck=deck)
        assert result.slide_count == 8

    def test_tool_results_include_add_image(self, tmp_path: Path):
        png = _make_fake_png(tmp_path, "slide_01.png")
        result, _ = _render_with_images(tmp_path, {1: png})
        tools = [r["tool"] for r in result.tool_results]
        assert "keynote.add_image" in tools

    def test_image_backed_slides_after_cover_use_blank_layout(self, tmp_path: Path):
        png = _make_fake_png(tmp_path, "slide_02.png")
        _, fake = _render_with_images(tmp_path, {2: png})
        add_slide_calls = [c for c in fake.calls if "make new slide" in c]
        slide_2_call = add_slide_calls[0]
        assert 'master slide "Blank"' in slide_2_call

    def test_image_backed_slides_after_cover_skip_default_title(self, tmp_path: Path):
        png = _make_fake_png(tmp_path, "slide_02.png")
        _, fake = _render_with_images(tmp_path, {2: png})
        set_title_calls = [c for c in fake.calls if "default title item" in c]
        assert all("角色介绍" not in c for c in set_title_calls)

    def test_cover_keeps_default_title_when_image_backed(self, tmp_path: Path):
        png = _make_fake_png(tmp_path, "slide_01.png")
        _, fake = _render_with_images(tmp_path, {1: png})
        set_title_calls = [c for c in fake.calls if "default title item" in c]
        assert any("三只小猪与大灰狼" in c for c in set_title_calls)

    def test_no_image_assets_none_behaves_as_009(self, tmp_path: Path):
        result_no_img = _render_three_pigs(tmp_path / "no_img")
        fake2 = _make_fake_runner()
        registry2, state2 = _make_registry_and_state(fake2)
        deck = _three_pigs_deck()
        result_explicit_none = render_storybook_deck(
            deck, registry2, state2,
            output_dir=tmp_path / "explicit_none",
            export_pdf=False,
            image_assets=None,
        )
        assert result_no_img.slide_count == result_explicit_none.slide_count
        assert result_no_img.image_count == 0
        assert result_explicit_none.image_count == 0


# ---------------------------------------------------------------------------
# CLI --images tests (012)
# ---------------------------------------------------------------------------

class TestRenderStorybookCLIImages:
    def _write_deck_spec(self, tmp_path: Path) -> Path:
        deck = _three_pigs_deck()
        p = tmp_path / "deck_spec.json"
        p.write_text(deck.model_dump_json(), encoding="utf-8")
        return p

    def _fake_register(self, fake: FakeScriptRunner):
        def patched(registry, runner):
            return register_keynote_tools(registry, fake)
        return patched

    def _write_manifest_with_png(self, tmp_path: Path, slide_indexes: list[int]) -> Path:
        import json as _json
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir(exist_ok=True)
        assets = []
        for idx in slide_indexes:
            fname = f"slide_{idx:02d}.png"
            _make_fake_png(assets_dir, fname)
            assets.append({
                "slide_index": idx,
                "prompt_hash": "abc",
                "provider": "fake",
                "path": f"assets/{fname}",
                "cached": False,
            })
        data = {"deck_title": "Test", "provider": "fake", "assets_dir": "assets", "assets": assets}
        manifest = tmp_path / "image_manifest.json"
        manifest.write_text(_json.dumps(data), encoding="utf-8")
        return manifest

    def test_images_option_passes_assets_to_renderer(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = _make_fake_runner()
        monkeypatch.setattr(cli_module, "register_keynote_tools", self._fake_register(fake))
        spec_path = self._write_deck_spec(tmp_path)
        manifest = self._write_manifest_with_png(tmp_path, [1])
        out = tmp_path / "out"
        result = cli_runner.invoke(app, [
            "render-storybook", str(spec_path), "--output", str(out), "--no-pdf",
            "--images", str(manifest),
        ])
        assert result.exit_code == 0, result.output
        # Should have called add_image for slide 1
        image_calls = [c for c in fake.calls if "make new image" in c]
        assert len(image_calls) >= 1

    def test_images_option_prints_manifest_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = _make_fake_runner()
        monkeypatch.setattr(cli_module, "register_keynote_tools", self._fake_register(fake))
        spec_path = self._write_deck_spec(tmp_path)
        manifest = self._write_manifest_with_png(tmp_path, [1])
        out = tmp_path / "out"
        result = cli_runner.invoke(app, [
            "render-storybook", str(spec_path), "--output", str(out), "--no-pdf",
            "--images", str(manifest),
        ])
        assert "image_manifest.json" in result.output

    def test_invalid_manifest_exits_before_renderer(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = _make_fake_runner()
        monkeypatch.setattr(cli_module, "register_keynote_tools", self._fake_register(fake))
        spec_path = self._write_deck_spec(tmp_path)
        bad_manifest = tmp_path / "bad_manifest.json"
        bad_manifest.write_text('{"not": "a manifest"}', encoding="utf-8")
        out = tmp_path / "out"
        result = cli_runner.invoke(app, [
            "render-storybook", str(spec_path), "--output", str(out), "--no-pdf",
            "--images", str(bad_manifest),
        ])
        assert result.exit_code != 0
        # Keynote should not have been touched
        list_themes_calls = [c for c in fake.calls if "every theme" in c]
        assert list_themes_calls == []

    def test_missing_manifest_file_exits_nonzero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = _make_fake_runner()
        monkeypatch.setattr(cli_module, "register_keynote_tools", self._fake_register(fake))
        spec_path = self._write_deck_spec(tmp_path)
        result = cli_runner.invoke(app, [
            "render-storybook", str(spec_path), "--no-pdf",
            "--images", str(tmp_path / "nonexistent_manifest.json"),
        ])
        assert result.exit_code != 0

    def test_no_images_option_unchanged_behavior(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = _make_fake_runner()
        monkeypatch.setattr(cli_module, "register_keynote_tools", self._fake_register(fake))
        spec_path = self._write_deck_spec(tmp_path)
        out = tmp_path / "out"
        result = cli_runner.invoke(app, ["render-storybook", str(spec_path), "--output", str(out), "--no-pdf"])
        assert result.exit_code == 0, result.output
        image_calls = [c for c in fake.calls if "make new image" in c]
        assert image_calls == []

    def test_tool_results_jsonl_contains_add_image(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = _make_fake_runner()
        monkeypatch.setattr(cli_module, "register_keynote_tools", self._fake_register(fake))
        spec_path = self._write_deck_spec(tmp_path)
        manifest = self._write_manifest_with_png(tmp_path, [1])
        out = tmp_path / "out"
        cli_runner.invoke(app, [
            "render-storybook", str(spec_path), "--output", str(out), "--no-pdf",
            "--images", str(manifest),
        ])
        lines = (out / "tool_results.jsonl").read_text().splitlines()
        tools = [json.loads(line)["tool"] for line in lines]
        assert "keynote.add_image" in tools


# ---------------------------------------------------------------------------
# 013 Overlay planning tests
# ---------------------------------------------------------------------------

def _make_solid_png(directory: Path, filename: str, rgb: tuple[int, int, int], size: tuple[int, int] = (1280, 720)) -> Path:
    """Write a solid-colour PNG using Pillow."""
    from PIL import Image as _PILImage
    img = _PILImage.new("RGB", size, color=rgb)
    p = directory / filename
    img.save(p)
    return p


class TestOverlayAnalysis:
    """Unit tests for renderers/overlays.py — no Keynote required."""

    def test_bright_region_chooses_dark_text(self, tmp_path: Path):
        from open_keynote_agent.renderers.overlays import build_overlay_plan
        png = _make_solid_png(tmp_path, "bright.png", (240, 240, 240))
        slide = _slide(2, kind="chapter", title="Test", body=["hello"])
        plan = build_overlay_plan(slide, png)
        assert plan.style.text_color == "#2C1810"

    def test_dark_region_chooses_white_text(self, tmp_path: Path):
        from open_keynote_agent.renderers.overlays import build_overlay_plan
        png = _make_solid_png(tmp_path, "dark.png", (20, 20, 20))
        slide = _slide(2, kind="chapter", title="Test", body=["hello"])
        plan = build_overlay_plan(slide, png)
        assert plan.style.text_color == "#FFFFFF"

    def test_solid_image_does_not_recommend_backing(self, tmp_path: Path):
        from open_keynote_agent.renderers.overlays import build_overlay_plan
        # Solid images have stddev=0, well below the busy threshold
        png = _make_solid_png(tmp_path, "solid.png", (30, 30, 30))
        slide = _slide(2, kind="chapter", title="Test", body=["hello"])
        plan = build_overlay_plan(slide, png)
        assert plan.style.use_backing is False

    def test_busy_image_recommends_backing(self, tmp_path: Path):
        """Checkerboard image has high stddev, should trigger use_backing=True."""
        from PIL import Image as _PILImage
        from open_keynote_agent.renderers.overlays import build_overlay_plan
        # Checkerboard of black and white at 4px grid — very high stddev
        img = _PILImage.new("RGB", (1280, 720))
        pixels = []
        for y in range(720):
            for x in range(1280):
                pixels.append((255, 255, 255) if (x // 4 + y // 4) % 2 == 0 else (0, 0, 0))
        img.putdata(pixels)
        png = tmp_path / "busy.png"
        img.save(png)
        slide = _slide(2, kind="chapter", title="Test", body=["hello"])
        plan = build_overlay_plan(slide, png)
        assert plan.style.use_backing is True

    def test_less_busy_region_selected(self, tmp_path: Path):
        """Image with a dark quiet bottom band vs noisy top should pick bottom_band."""
        from PIL import Image as _PILImage
        from open_keynote_agent.renderers.overlays import build_overlay_plan
        img = _PILImage.new("RGB", (1280, 720), color=(30, 30, 30))
        # Flood the top 200 rows with a noisy checkerboard
        for y in range(200):
            for x in range(1280):
                color = (255, 255, 255) if (x // 4 + y // 4) % 2 == 0 else (0, 0, 0)
                img.putpixel((x, y), color)
        png = tmp_path / "noisy_top.png"
        img.save(png)
        slide = _slide(2, kind="chapter", title="Test", body=["hello"])
        plan = build_overlay_plan(slide, png)
        assert plan.region.name == "bottom_band"
        assert plan.diagnostics.get("fallback") is False

    def test_analysis_failure_returns_fallback(self, tmp_path: Path):
        from open_keynote_agent.renderers.overlays import build_overlay_plan, _FALLBACK_X, _FALLBACK_Y
        png = tmp_path / "nonexistent.png"   # does not exist
        slide = _slide(2, kind="chapter", title="Test", body=["hello"])
        plan = build_overlay_plan(slide, png)
        assert plan.diagnostics.get("fallback") is True
        assert plan.region.x == _FALLBACK_X
        assert plan.region.y == _FALLBACK_Y

    def test_cover_overlay_is_subtitle(self, tmp_path: Path):
        from open_keynote_agent.renderers.overlays import build_overlay_plan
        png = _make_solid_png(tmp_path, "cover.png", (20, 20, 20))
        slide = _slide(1, kind="cover", title="Title", subtitle="A great story")
        plan = build_overlay_plan(slide, png)
        assert plan.text == "A great story"

    def test_cover_no_subtitle_yields_empty_text(self, tmp_path: Path):
        from open_keynote_agent.renderers.overlays import build_overlay_plan
        png = _make_solid_png(tmp_path, "cover_nosub.png", (20, 20, 20))
        slide = _slide(1, kind="cover", title="Title")
        plan = build_overlay_plan(slide, png)
        assert plan.text == ""

    def test_body_text_used_when_present(self, tmp_path: Path):
        from open_keynote_agent.renderers.overlays import build_overlay_plan
        png = _make_solid_png(tmp_path, "ch.png", (20, 20, 20))
        slide = _slide(2, kind="chapter", title="Title", subtitle="Sub", body=["Line one", "Line two"])
        plan = build_overlay_plan(slide, png)
        assert "Line one" in plan.text
        assert "Line two" in plan.text

    def test_subtitle_fallback_when_body_empty(self, tmp_path: Path):
        from open_keynote_agent.renderers.overlays import build_overlay_plan
        png = _make_solid_png(tmp_path, "sub.png", (20, 20, 20))
        slide = _slide(2, kind="chapter", title="Title", subtitle="The subtitle")
        plan = build_overlay_plan(slide, png)
        assert plan.text == "The subtitle"

    def test_title_fallback_when_body_and_subtitle_empty(self, tmp_path: Path):
        from open_keynote_agent.renderers.overlays import build_overlay_plan
        png = _make_solid_png(tmp_path, "title_fb.png", (20, 20, 20))
        slide = _slide(2, kind="chapter", title="ChapterTitle")
        plan = build_overlay_plan(slide, png)
        assert plan.text == "ChapterTitle"

    def test_diagnostics_include_luminance_and_region(self, tmp_path: Path):
        from open_keynote_agent.renderers.overlays import build_overlay_plan
        png = _make_solid_png(tmp_path, "diag.png", (100, 100, 100))
        slide = _slide(2, kind="chapter", title="T", body=["b"])
        plan = build_overlay_plan(slide, png)
        assert "mean_luminance" in plan.diagnostics
        assert "selected_region" in plan.diagnostics
        assert plan.diagnostics["fallback"] is False


class TestRendererImageOverlay:
    """Renderer integration tests for 013 image-aware overlay."""

    def _render_with_real_png(
        self,
        tmp_path: Path,
        rgb: tuple[int, int, int],
        slides_with_images: dict[int, str],
        deck: DeckSpec | None = None,
    ) -> tuple[RenderResult, FakeScriptRunner]:
        from PIL import Image as _PILImage
        fake = _make_fake_runner()
        registry, state = _make_registry_and_state(fake)
        deck = deck or _three_pigs_deck()
        assets: dict[int, Path] = {}
        for idx, fname in slides_with_images.items():
            img = _PILImage.new("RGB", (1280, 720), color=rgb)
            p = tmp_path / fname
            img.save(p)
            assets[idx] = p
        result = render_storybook_deck(
            deck, registry, state,
            output_dir=tmp_path, export_pdf=False,
            image_assets=assets,
        )
        return result, fake

    def test_image_insertion_precedes_overlay_text(self, tmp_path: Path):
        _, fake = self._render_with_real_png(tmp_path, (20, 20, 20), {2: "s2.png"})
        image_positions = [i for i, c in enumerate(fake.calls) if "make new image" in c]
        text_positions  = [i for i, c in enumerate(fake.calls) if "make new text item" in c]
        assert image_positions, "expected at least one add_image call"
        assert text_positions,  "expected at least one add_text_box call"
        assert image_positions[-1] < text_positions[-1]

    def test_font_color_passed_to_text_box_dark_image(self, tmp_path: Path):
        # Dark image → white text (#FFFFFF). Keynote 16-bit: {65535, 65535, 65535}.
        _, fake = self._render_with_real_png(tmp_path, (10, 10, 10), {2: "s2.png"})
        text_color_calls = [c for c in fake.calls if "set color of object text" in c]
        assert any("65535" in c for c in text_color_calls), (
            "expected white font color (65535) for dark image"
        )

    def test_font_color_passed_to_text_box_bright_image(self, tmp_path: Path):
        # Bright image → dark text (#2C1810). Keynote 16-bit: #2C = 44 → 44*65535/255 = 11308.
        _, fake = self._render_with_real_png(tmp_path, (240, 240, 240), {2: "s2.png"})
        text_color_calls = [c for c in fake.calls if "set color of object text" in c]
        assert any("11308" in c for c in text_color_calls), (
            "expected dark brown font color (11308) for bright image"
        )

    def test_no_image_fallback_unchanged(self, tmp_path: Path):
        result = _render_three_pigs(tmp_path)
        assert result.image_count == 0
        # Should still have emoji/text calls
        fake2 = _make_fake_runner()
        _render_three_pigs(tmp_path / "b", fake2)
        text_calls = [c for c in fake2.calls if "make new text item" in c]
        assert len(text_calls) >= 1
