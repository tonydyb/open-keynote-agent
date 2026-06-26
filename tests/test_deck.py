"""Tests for the deck spec planning layer (change 008).

No cloud credentials, Keynote, osascript, or macOS Automation permissions required.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

import open_keynote_agent.cli as cli_module
from open_keynote_agent.cli import app
from open_keynote_agent.deck.outline import render_deck_outline
from open_keynote_agent.deck.planner import plan_deck_spec
from open_keynote_agent.deck.schema import DeckSpec, SlideSpec, StyleSpec, VisualSpec
from open_keynote_agent.llm.fake import FakeLLMClient

cli_runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_visual(**kw) -> dict:
    base: dict[str, Any] = {"description": "A cozy storybook scene"}
    base.update(kw)
    return base


def _make_slide(index: int, kind: str = "content", title: str = "Slide", **kw) -> dict:
    base: dict[str, Any] = {
        "index": index,
        "kind": kind,
        "title": title,
        "visual": _make_visual(),
    }
    base.update(kw)
    return base


def _make_style(**kw) -> dict:
    base: dict[str, Any] = {"mood": "warm and cheerful"}
    base.update(kw)
    return base


def _minimal_deck(n_slides: int = 1) -> dict:
    return {
        "title": "Test Deck",
        "style": _make_style(),
        "slides": [_make_slide(i) for i in range(1, n_slides + 1)],
    }


THREE_PIGS_RESPONSE: dict[str, Any] = {
    "title": "三只小猪与大灰狼",
    "subtitle": "一个关于勤劳和勇敢的故事",
    "language": "zh",
    "theme": "Parchment",
    "style": {
        "mood": "童话绘本风，温暖可爱",
        "audience": "儿童",
        "palette": ["orange", "yellow", "brown", "green"],
        "avoid": ["blue business style"],
        "typography": "large playful titles, readable body text",
    },
    "slides": [
        {
            "index": 1,
            "kind": "cover",
            "title": "三只小猪与大灰狼",
            "subtitle": "一个关于勤劳和勇敢的故事",
            "body": [],
            "visual": {
                "description": "Three cute pigs and a wolf in a warm storybook style",
                "emoji": ["🐷", "🐷", "🐷", "🐺"],
                "decorations": ["warm parchment frame", "small straw/wood/brick motifs"],
                "placement_hint": "large visual cluster on the right",
            },
        },
        {
            "index": 2,
            "kind": "characters",
            "title": "认识三只小猪",
            "body": ["大毛：贪玩，喜欢稻草屋", "二毛：聪明一点，但还不够努力", "小毛：勤劳、有耐心"],
            "visual": {
                "description": "Three pig character portraits side by side",
                "emoji": ["🐷", "🐷", "🐷"],
                "decorations": [],
            },
        },
        {
            "index": 3,
            "kind": "chapter",
            "title": "第一章 — 大毛的稻草屋",
            "body": ["大毛用稻草盖了一间小屋", "他觉得这样就够了"],
            "visual": {
                "description": "A straw house in a sunny meadow",
                "emoji": ["🌾", "🏠"],
                "decorations": ["golden straw bundles"],
            },
        },
        {
            "index": 4,
            "kind": "chapter",
            "title": "第二章 — 二毛的木屋",
            "body": ["二毛用木头盖了一间木屋", "他觉得已经比大毛强了"],
            "visual": {
                "description": "A wooden house in the forest",
                "emoji": ["🪵", "🏠"],
                "decorations": ["wooden planks motif"],
            },
        },
        {
            "index": 5,
            "kind": "chapter",
            "title": "第三章 — 小毛的砖房",
            "body": ["小毛花了很长时间用砖块盖了坚固的房子"],
            "visual": {
                "description": "A solid brick house",
                "emoji": ["🧱", "🏠"],
                "decorations": ["brick wall pattern"],
            },
        },
        {
            "index": 6,
            "kind": "climax",
            "title": "大灰狼来了！",
            "body": ["大灰狼吹倒了稻草屋", "又吹倒了木屋", "但吹不动砖房！"],
            "visual": {
                "description": "Wolf blowing at houses, pigs running to brick house",
                "emoji": ["🐺", "💨", "🏠"],
                "decorations": ["dramatic storm clouds"],
            },
        },
        {
            "index": 7,
            "kind": "lesson",
            "title": "勤劳的力量",
            "body": ["努力和耐心才能保护我们", "不要走捷径"],
            "visual": {
                "description": "Three pigs safe inside the brick house, wolf retreating",
                "emoji": ["🐷", "🐷", "🐷", "✨"],
                "decorations": ["warm glow, heart motifs"],
            },
        },
        {
            "index": 8,
            "kind": "ending",
            "title": "The End",
            "body": [],
            "visual": {
                "description": "Storybook closing page with flower border",
                "emoji": ["🌸", "📖"],
                "decorations": ["floral border", "soft pastel background"],
            },
        },
    ],
}


# ---------------------------------------------------------------------------
# StyleSpec
# ---------------------------------------------------------------------------

class TestStyleSpec:
    def test_valid(self):
        s = StyleSpec(mood="warm")
        assert s.mood == "warm"

    def test_blank_mood_rejected(self):
        with pytest.raises(ValidationError, match="mood"):
            StyleSpec(mood="   ")

    def test_optional_fields_default(self):
        s = StyleSpec(mood="cheerful")
        assert s.audience is None
        assert s.palette == []
        assert s.avoid == []
        assert s.typography is None

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            StyleSpec(mood="warm", unknown_field="x")


# ---------------------------------------------------------------------------
# VisualSpec
# ---------------------------------------------------------------------------

class TestVisualSpec:
    def test_valid_minimal(self):
        v = VisualSpec(description="A scene")
        assert v.description == "A scene"
        assert v.emoji == []
        assert v.decorations == []

    def test_blank_description_rejected(self):
        with pytest.raises(ValidationError, match="description"):
            VisualSpec(description="  ")

    def test_emoji_items_nonempty(self):
        with pytest.raises(ValidationError):
            VisualSpec(description="x", emoji=["🐷", ""])

    def test_emoji_must_be_list(self):
        with pytest.raises(ValidationError):
            VisualSpec(description="x", emoji=None)

    def test_decoration_items_nonempty(self):
        with pytest.raises(ValidationError):
            VisualSpec(description="x", decorations=["border", ""])

    def test_decorations_must_be_list(self):
        with pytest.raises(ValidationError):
            VisualSpec(description="x", decorations=None)

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            VisualSpec(description="x", unknown="y")


# ---------------------------------------------------------------------------
# SlideSpec
# ---------------------------------------------------------------------------

class TestSlideSpec:
    def test_valid(self):
        s = SlideSpec(
            index=1, kind="cover", title="Cover",
            visual=VisualSpec(description="cover scene"),
        )
        assert s.index == 1

    def test_index_zero_rejected(self):
        with pytest.raises(ValidationError, match="index"):
            SlideSpec(index=0, kind="cover", title="x", visual=VisualSpec(description="x"))

    def test_blank_title_rejected(self):
        with pytest.raises(ValidationError, match="title"):
            SlideSpec(index=1, kind="cover", title="  ", visual=VisualSpec(description="x"))

    def test_invalid_kind_rejected(self):
        with pytest.raises(ValidationError):
            SlideSpec(index=1, kind="unknown_kind", title="x", visual=VisualSpec(description="x"))

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            SlideSpec(index=1, kind="cover", title="x", visual=VisualSpec(description="x"), extra="y")


# ---------------------------------------------------------------------------
# DeckSpec
# ---------------------------------------------------------------------------

class TestDeckSpec:
    def test_valid_minimal(self):
        d = DeckSpec(**_minimal_deck())
        assert d.title == "Test Deck"
        assert len(d.slides) == 1

    def test_blank_title_rejected(self):
        data = _minimal_deck()
        data["title"] = "  "
        with pytest.raises(ValidationError, match="title"):
            DeckSpec(**data)

    def test_zero_slides_rejected(self):
        data = _minimal_deck()
        data["slides"] = []
        with pytest.raises(ValidationError, match="slides"):
            DeckSpec(**data)

    def test_21_slides_rejected(self):
        data = _minimal_deck(n_slides=21)
        with pytest.raises(ValidationError, match="slides"):
            DeckSpec(**data)

    def test_20_slides_accepted(self):
        d = DeckSpec(**_minimal_deck(n_slides=20))
        assert len(d.slides) == 20

    def test_nonsequential_indexes_rejected(self):
        data = _minimal_deck(n_slides=2)
        data["slides"][1]["index"] = 3  # should be 2
        with pytest.raises(ValidationError, match="sequential"):
            DeckSpec(**data)

    def test_extra_field_rejected(self):
        data = _minimal_deck()
        data["unknown"] = "x"
        with pytest.raises(ValidationError):
            DeckSpec(**data)

    def test_language_defaults_to_none(self):
        d = DeckSpec(**_minimal_deck())
        assert d.language is None

    def test_theme_defaults_to_parchment(self):
        d = DeckSpec(**_minimal_deck())
        assert d.theme == "Parchment"

    def test_three_pigs_fixture_valid(self):
        d = DeckSpec(**THREE_PIGS_RESPONSE)
        assert len(d.slides) == 8
        assert d.title == "三只小猪与大灰狼"

    def test_three_pigs_all_slides_have_visual(self):
        d = DeckSpec(**THREE_PIGS_RESPONSE)
        for slide in d.slides:
            assert slide.visual.description.strip()

    def test_three_pigs_style_avoids_business(self):
        d = DeckSpec(**THREE_PIGS_RESPONSE)
        assert any("blue business" in a for a in d.style.avoid)

    def test_three_pigs_theme_parchment(self):
        d = DeckSpec(**THREE_PIGS_RESPONSE)
        assert d.theme == "Parchment"


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

class TestPlanDeckSpec:
    def test_blank_brief_rejected_before_llm(self):
        fake = FakeLLMClient()
        with pytest.raises(ValueError, match="blank"):
            plan_deck_spec("  ", fake)
        assert fake.calls == []

    def test_whitespace_only_brief_rejected(self):
        fake = FakeLLMClient()
        with pytest.raises(ValueError, match="blank"):
            plan_deck_spec("\n\t", fake)
        assert fake.calls == []

    def test_slide_count_hint_zero_rejected(self):
        fake = FakeLLMClient()
        with pytest.raises(ValueError, match="slide_count_hint"):
            plan_deck_spec("a brief", fake, slide_count_hint=0)
        assert fake.calls == []

    def test_slide_count_hint_21_rejected(self):
        fake = FakeLLMClient()
        with pytest.raises(ValueError, match="slide_count_hint"):
            plan_deck_spec("a brief", fake, slide_count_hint=21)
        assert fake.calls == []

    def test_slide_count_hint_1_accepted(self):
        fake = FakeLLMClient(response=_minimal_deck())
        plan_deck_spec("brief", fake, slide_count_hint=1)
        assert len(fake.calls) == 1

    def test_slide_count_hint_20_accepted(self):
        fake = FakeLLMClient(response=_minimal_deck())
        plan_deck_spec("brief", fake, slide_count_hint=20)
        assert len(fake.calls) == 1

    def test_passes_json_schema_to_client(self):
        fake = FakeLLMClient(response=_minimal_deck())
        plan_deck_spec("brief", fake)
        assert len(fake.calls) == 1
        schema = fake.calls[0]["schema"]
        assert schema == DeckSpec.model_json_schema()

    def test_json_schema_exposes_slide_index_and_count_constraints(self):
        schema = DeckSpec.model_json_schema()
        slide_spec = schema["$defs"]["SlideSpec"]
        assert slide_spec["properties"]["index"]["minimum"] == 1
        assert schema["properties"]["slides"]["minItems"] == 1
        assert schema["properties"]["slides"]["maxItems"] == 20

    def test_returns_validated_deck_spec(self):
        fake = FakeLLMClient(response=_minimal_deck())
        deck = plan_deck_spec("brief", fake)
        assert isinstance(deck, DeckSpec)

    def test_invalid_llm_response_raises_value_error(self):
        fake = FakeLLMClient(response={"title": "", "style": {"mood": "x"}, "slides": []})
        with pytest.raises(ValueError, match="DeckSpec schema"):
            plan_deck_spec("brief", fake)

    def test_malformed_llm_response_raises_value_error(self):
        fake = FakeLLMClient(response={"completely": "wrong"})
        with pytest.raises(ValueError, match="DeckSpec schema"):
            plan_deck_spec("brief", fake)

    def test_theme_hint_included_in_messages(self):
        fake = FakeLLMClient(response=_minimal_deck())
        plan_deck_spec("brief", fake, theme_hint="Basic White")
        messages = fake.calls[0]["messages"]
        system_content = messages[0]["content"]
        assert "Basic White" in system_content

    def test_slide_count_hint_included_in_messages(self):
        fake = FakeLLMClient(response=_minimal_deck())
        plan_deck_spec("brief", fake, slide_count_hint=5)
        messages = fake.calls[0]["messages"]
        system_content = messages[0]["content"]
        assert "5" in system_content

    def test_index_instruction_included_in_messages(self):
        fake = FakeLLMClient(response=_minimal_deck())
        plan_deck_spec("brief", fake)
        messages = fake.calls[0]["messages"]
        system_content = messages[0]["content"]
        assert "starting at 1" in system_content

    def test_three_pigs_response_parsed(self):
        fake = FakeLLMClient(response=THREE_PIGS_RESPONSE)
        deck = plan_deck_spec("三只小猪故事", fake, slide_count_hint=8)
        assert len(deck.slides) == 8
        assert deck.title == "三只小猪与大灰狼"

    def test_does_not_import_keynote_tools(self):
        import open_keynote_agent.deck.planner as planner_mod
        source = planner_mod.__file__
        assert source is not None
        content = Path(source).read_text()
        assert "tools.keynote" not in content
        assert "OsascriptRunner" not in content
        assert "applescript" not in content


# ---------------------------------------------------------------------------
# Outline renderer
# ---------------------------------------------------------------------------

class TestRenderDeckOutline:
    def test_contains_title(self):
        deck = DeckSpec(**_minimal_deck())
        out = render_deck_outline(deck)
        assert "Test Deck" in out

    def test_contains_theme(self):
        deck = DeckSpec(**_minimal_deck())
        out = render_deck_outline(deck)
        assert "Parchment" in out

    def test_contains_style(self):
        deck = DeckSpec(**_minimal_deck())
        out = render_deck_outline(deck)
        assert "warm and cheerful" in out

    def test_contains_slide_number(self):
        deck = DeckSpec(**_minimal_deck())
        out = render_deck_outline(deck)
        assert "1." in out

    def test_contains_slide_title(self):
        deck = DeckSpec(**_minimal_deck())
        out = render_deck_outline(deck)
        assert "Slide" in out

    def test_contains_visual_description(self):
        deck = DeckSpec(**_minimal_deck())
        out = render_deck_outline(deck)
        assert "A cozy storybook scene" in out

    def test_contains_body_bullets(self):
        data = _minimal_deck()
        data["slides"][0]["body"] = ["bullet one", "bullet two"]
        deck = DeckSpec(**data)
        out = render_deck_outline(deck)
        assert "bullet one" in out
        assert "bullet two" in out

    def test_contains_emoji(self):
        data = _minimal_deck()
        data["slides"][0]["visual"]["emoji"] = ["🐷", "🐺"]
        deck = DeckSpec(**data)
        out = render_deck_outline(deck)
        assert "🐷" in out
        assert "🐺" in out

    def test_contains_decorations(self):
        data = _minimal_deck()
        data["slides"][0]["visual"]["decorations"] = ["parchment frame"]
        deck = DeckSpec(**data)
        out = render_deck_outline(deck)
        assert "parchment frame" in out

    def test_subtitle_included_when_present(self):
        data = _minimal_deck()
        data["subtitle"] = "A beautiful story"
        deck = DeckSpec(**data)
        out = render_deck_outline(deck)
        assert "A beautiful story" in out

    def test_no_subtitle_when_absent(self):
        deck = DeckSpec(**_minimal_deck())
        out = render_deck_outline(deck)
        assert "None" not in out

    def test_three_pigs_outline(self):
        deck = DeckSpec(**THREE_PIGS_RESPONSE)
        out = render_deck_outline(deck)
        assert "三只小猪与大灰狼" in out
        assert "Parchment" in out
        assert "🐷" in out
        assert "8." in out

    def test_output_ends_with_newline(self):
        deck = DeckSpec(**_minimal_deck())
        out = render_deck_outline(deck)
        assert out.endswith("\n")

    def test_deterministic_output(self):
        deck = DeckSpec(**_minimal_deck())
        assert render_deck_outline(deck) == render_deck_outline(deck)


# ---------------------------------------------------------------------------
# CLI: deck-plan command
# ---------------------------------------------------------------------------

class TestDeckPlanCLI:
    def _fake_client(self) -> FakeLLMClient:
        return FakeLLMClient(response=_minimal_deck())

    def test_writes_three_output_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = self._fake_client()
        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: fake)
        result = cli_runner.invoke(app, ["deck-plan", "Make a deck", "--output", str(tmp_path / "out")])
        assert result.exit_code == 0, result.output
        out = tmp_path / "out"
        assert (out / "request.json").exists()
        assert (out / "deck_spec.json").exists()
        assert (out / "outline.md").exists()

    def test_request_json_contains_brief(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = self._fake_client()
        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: fake)
        cli_runner.invoke(app, ["deck-plan", "My brief text", "--output", str(tmp_path / "out")])
        data = json.loads((tmp_path / "out" / "request.json").read_text())
        assert data["brief"] == "My brief text"

    def test_deck_spec_json_is_valid_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = self._fake_client()
        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: fake)
        cli_runner.invoke(app, ["deck-plan", "brief", "--output", str(tmp_path / "out")])
        parsed = json.loads((tmp_path / "out" / "deck_spec.json").read_text())
        assert "title" in parsed

    def test_outline_md_contains_title(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = self._fake_client()
        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: fake)
        cli_runner.invoke(app, ["deck-plan", "brief", "--output", str(tmp_path / "out")])
        content = (tmp_path / "out" / "outline.md").read_text()
        assert "Test Deck" in content

    def test_outline_printed_to_terminal(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = self._fake_client()
        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: fake)
        result = cli_runner.invoke(app, ["deck-plan", "brief", "--output", str(tmp_path / "out")])
        assert "Test Deck" in result.output

    def test_refuses_to_overwrite_existing_request_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = self._fake_client()
        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: fake)
        out = tmp_path / "out"
        out.mkdir()
        (out / "request.json").write_text("{}")
        result = cli_runner.invoke(app, ["deck-plan", "brief", "--output", str(out)])
        assert result.exit_code != 0

    def test_refuses_to_overwrite_existing_deck_spec_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = self._fake_client()
        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: fake)
        out = tmp_path / "out"
        out.mkdir()
        (out / "deck_spec.json").write_text("{}")
        result = cli_runner.invoke(app, ["deck-plan", "brief", "--output", str(out)])
        assert result.exit_code != 0

    def test_refuses_to_overwrite_existing_outline_md(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = self._fake_client()
        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: fake)
        out = tmp_path / "out"
        out.mkdir()
        (out / "outline.md").write_text("# old")
        result = cli_runner.invoke(app, ["deck-plan", "brief", "--output", str(out)])
        assert result.exit_code != 0

    def test_default_output_under_runs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = self._fake_client()
        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: fake)
        result = cli_runner.invoke(app, ["deck-plan", "brief"])
        assert result.exit_code == 0, result.output
        runs_dir = tmp_path / ".runs"
        assert runs_dir.exists()
        run_dirs = list(runs_dir.iterdir())
        assert len(run_dirs) == 1
        assert (run_dirs[0] / "deck_spec.json").exists()

    def test_slides_option_passed_to_planner(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = self._fake_client()
        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: fake)
        cli_runner.invoke(app, ["deck-plan", "brief", "--slides", "5", "--output", str(tmp_path / "out")])
        messages = fake.calls[0]["messages"]
        system_msg = messages[0]["content"]
        assert "5" in system_msg

    def test_theme_option_passed_to_planner(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = self._fake_client()
        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: fake)
        cli_runner.invoke(app, ["deck-plan", "brief", "--theme", "Craft", "--output", str(tmp_path / "out")])
        messages = fake.calls[0]["messages"]
        system_msg = messages[0]["content"]
        assert "Craft" in system_msg

    def test_deck_spec_json_ensure_ascii_false(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = FakeLLMClient(response=THREE_PIGS_RESPONSE)
        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: fake)
        cli_runner.invoke(app, ["deck-plan", "三只小猪", "--output", str(tmp_path / "out")])
        raw = (tmp_path / "out" / "deck_spec.json").read_bytes()
        assert "三只小猪".encode() in raw

    def test_validation_error_exits_nonzero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = FakeLLMClient(response={"bad": "response"})
        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: fake)
        result = cli_runner.invoke(app, ["deck-plan", "brief", "--output", str(tmp_path / "out")])
        assert result.exit_code != 0

    def test_llm_load_error_exits_nonzero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)

        def _raise_load_error():
            raise RuntimeError("provider unavailable")

        monkeypatch.setattr(cli_module, "load_llm_client_from_env", _raise_load_error)
        result = cli_runner.invoke(app, ["deck-plan", "brief", "--output", str(tmp_path / "out")])
        assert result.exit_code != 0
        assert "provider unavailable" in result.output
        assert not (tmp_path / "out" / "request.json").exists()

    def test_llm_completion_error_exits_nonzero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)

        class RaisingLLM:
            def complete_json(self, messages, schema):
                raise RuntimeError("completion failed")

        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: RaisingLLM())
        result = cli_runner.invoke(app, ["deck-plan", "brief", "--output", str(tmp_path / "out")])
        assert result.exit_code != 0
        assert "completion failed" in result.output
        assert not (tmp_path / "out" / "request.json").exists()

    def test_failure_does_not_write_partial_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = FakeLLMClient(response={"bad": "response"})
        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: fake)
        out = tmp_path / "out"
        cli_runner.invoke(app, ["deck-plan", "brief", "--output", str(out)])
        assert not (out / "request.json").exists()
        assert not (out / "deck_spec.json").exists()
        assert not (out / "outline.md").exists()

    def test_default_dir_cleaned_up_on_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        fake = FakeLLMClient(response={"bad": "response"})
        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: fake)
        result = cli_runner.invoke(app, ["deck-plan", "brief"])
        assert result.exit_code != 0
        # The auto-created .runs directory should not have been left behind
        runs_dir = tmp_path / ".runs"
        if runs_dir.exists():
            leftover = list(runs_dir.iterdir())
            assert leftover == [], f"Unexpected leftover dirs: {leftover}"

    def test_timestamp_collision_gets_suffix(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        from datetime import UTC, datetime as real_dt

        monkeypatch.chdir(tmp_path)
        fixed_ts = "20260101T000000Z"

        class _FakeDatetime:
            @staticmethod
            def now(tz=None):
                return real_dt(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

            @staticmethod
            def strftime(dt_obj, fmt):
                return real_dt.strftime(dt_obj, fmt)

        monkeypatch.setattr(cli_module, "datetime", _FakeDatetime)

        # Pre-create the expected default dir to force collision
        (tmp_path / ".runs" / fixed_ts).mkdir(parents=True)

        fake = self._fake_client()
        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: fake)
        result = cli_runner.invoke(app, ["deck-plan", "brief"])
        assert result.exit_code == 0, result.output
        # The collision dir should have been avoided — a -1 suffix dir created
        assert (tmp_path / ".runs" / f"{fixed_ts}-1" / "deck_spec.json").exists()
