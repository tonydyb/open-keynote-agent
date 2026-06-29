"""Tests for the image asset generation layer (change 010).

No network, real image API credentials, Keynote, osascript, or macOS Automation required.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

import open_keynote_agent.cli as cli_module
from open_keynote_agent.cli import app
from open_keynote_agent.deck.schema import DeckSpec
from open_keynote_agent.images.generator import _prompt_hash, generate_image_assets
from open_keynote_agent.images.planner import _NO_TEXT_INSTRUCTION, build_slide_art_specs
from open_keynote_agent.images.provider import (
    FakeImageProvider,
    UnsupportedImageProviderError,
    load_image_provider_from_env,
)
from open_keynote_agent.images.schema import ImageManifest, ImageSpec, SlideArtSpec

cli_runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_visual(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"description": "A cozy storybook scene"}
    base.update(kw)
    return base


def _make_slide(index: int, kind: str = "content", title: str = "Slide", **kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "index": index,
        "kind": kind,
        "title": title,
        "visual": _make_visual(),
    }
    base.update(kw)
    return base


def _make_style(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"mood": "warm and cheerful"}
    base.update(kw)
    return base


def _minimal_deck_dict(n_slides: int = 3) -> dict[str, Any]:
    slides = [_make_slide(1, kind="cover", title="Cover")]
    for i in range(2, n_slides + 1):
        slides.append(_make_slide(i, kind="chapter", title=f"Chapter {i}"))
    return {
        "title": "Three Little Pigs",
        "style": _make_style(
            mood="童话绘本风，温暖可爱",
            audience="children",
            palette=["orange", "yellow", "brown"],
        ),
        "slides": slides,
    }


def _three_pigs_deck() -> DeckSpec:
    return DeckSpec(**_minimal_deck_dict(n_slides=4))


def _write_deck_spec(tmp_path: Path, n_slides: int = 3) -> Path:
    p = tmp_path / "deck_spec.json"
    p.write_text(
        json.dumps(_minimal_deck_dict(n_slides), ensure_ascii=False),
        encoding="utf-8",
    )
    return p


# ---------------------------------------------------------------------------
# ImageSpec validation
# ---------------------------------------------------------------------------

class TestImageSpec:
    def test_valid_minimal(self):
        spec = ImageSpec(prompt="A cute pig house")
        assert spec.prompt == "A cute pig house"
        assert spec.output_format == "png"
        assert spec.aspect_ratio == "16:9"

    def test_blank_prompt_raises(self):
        with pytest.raises(ValidationError):
            ImageSpec(prompt="   ")

    def test_empty_prompt_raises(self):
        with pytest.raises(ValidationError):
            ImageSpec(prompt="")

    def test_unsupported_aspect_ratio_raises(self):
        with pytest.raises(ValidationError):
            ImageSpec(prompt="x", aspect_ratio="4:3")

    def test_output_format_must_be_png(self):
        with pytest.raises(ValidationError):
            ImageSpec(prompt="x", output_format="jpg")  # type: ignore[arg-type]

    def test_optional_fields_default(self):
        spec = ImageSpec(prompt="x")
        assert spec.negative_prompt is None
        assert spec.seed is None

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            ImageSpec(prompt="x", unknown_field="y")


# ---------------------------------------------------------------------------
# SlideArtSpec validation
# ---------------------------------------------------------------------------

class TestSlideArtSpec:
    def test_asset_filename_computed(self):
        spec = SlideArtSpec(
            slide_index=3,
            slide_title="Chapter Three",
            image=ImageSpec(prompt="A brick house"),
        )
        assert spec.asset_filename == "slide_03.png"

    def test_asset_filename_slide_01(self):
        spec = SlideArtSpec(
            slide_index=1,
            slide_title="Cover",
            image=ImageSpec(prompt="Three pigs"),
        )
        assert spec.asset_filename == "slide_01.png"

    def test_asset_filename_slide_12(self):
        spec = SlideArtSpec(
            slide_index=12,
            slide_title="Ending",
            image=ImageSpec(prompt="Happy pigs"),
        )
        assert spec.asset_filename == "slide_12.png"

    def test_slide_index_ge_one(self):
        with pytest.raises(ValidationError):
            SlideArtSpec(
                slide_index=0,
                slide_title="Bad",
                image=ImageSpec(prompt="x"),
            )

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            SlideArtSpec(
                slide_index=1,
                slide_title="x",
                image=ImageSpec(prompt="x"),
                bad_field="y",
            )


# ---------------------------------------------------------------------------
# Art spec planner
# ---------------------------------------------------------------------------

class TestBuildSlideArtSpecs:
    def test_one_spec_per_slide(self):
        deck = _three_pigs_deck()
        specs = build_slide_art_specs(deck)
        assert len(specs) == len(deck.slides)

    def test_sequential_indexes(self):
        deck = _three_pigs_deck()
        specs = build_slide_art_specs(deck)
        assert [s.slide_index for s in specs] == [s.index for s in deck.slides]

    def test_slide_titles_match(self):
        deck = _three_pigs_deck()
        specs = build_slide_art_specs(deck)
        for spec, slide in zip(specs, deck.slides):
            assert spec.slide_title == slide.title

    def test_prompt_contains_deck_title(self):
        deck = _three_pigs_deck()
        specs = build_slide_art_specs(deck)
        for spec in specs:
            assert "Three Little Pigs" in spec.image.prompt

    def test_prompt_contains_slide_title(self):
        deck = _three_pigs_deck()
        specs = build_slide_art_specs(deck)
        for spec, slide in zip(specs, deck.slides):
            assert slide.title in spec.image.prompt

    def test_prompt_contains_no_text_instruction(self):
        deck = _three_pigs_deck()
        specs = build_slide_art_specs(deck)
        for spec in specs:
            assert _NO_TEXT_INSTRUCTION in spec.image.prompt

    def test_prompt_contains_mood(self):
        deck = _three_pigs_deck()
        specs = build_slide_art_specs(deck)
        for spec in specs:
            assert deck.style.mood in spec.image.prompt

    def test_prompt_contains_audience(self):
        deck = _three_pigs_deck()
        specs = build_slide_art_specs(deck)
        for spec in specs:
            assert "children" in spec.image.prompt

    def test_prompt_contains_visual_description(self):
        deck = _three_pigs_deck()
        specs = build_slide_art_specs(deck)
        for spec, slide in zip(specs, deck.slides):
            assert slide.visual.description in spec.image.prompt

    def test_prompt_contains_emoji_when_present(self):
        raw = _minimal_deck_dict(n_slides=1)
        raw["slides"][0]["visual"]["emoji"] = ["🐷", "🏠"]
        deck = DeckSpec(**raw)
        specs = build_slide_art_specs(deck)
        assert "🐷" in specs[0].image.prompt
        assert "🏠" in specs[0].image.prompt

    def test_prompt_contains_palette(self):
        deck = _three_pigs_deck()
        specs = build_slide_art_specs(deck)
        for spec in specs:
            assert "orange" in spec.image.prompt

    def test_prompt_contains_body_bullets(self):
        raw = _minimal_deck_dict(n_slides=1)
        raw["slides"][0]["body"] = ["Straw house", "Mud walls"]
        deck = DeckSpec(**raw)
        specs = build_slide_art_specs(deck)
        assert "Straw house" in specs[0].image.prompt

    def test_deterministic(self):
        deck = _three_pigs_deck()
        specs_a = build_slide_art_specs(deck)
        specs_b = build_slide_art_specs(deck)
        assert [s.image.prompt for s in specs_a] == [s.image.prompt for s in specs_b]

    def test_does_not_call_llm(self):
        import open_keynote_agent.images.planner as planner_mod
        source = planner_mod.__file__
        assert source is not None
        content = Path(source).read_text()
        assert "LLMClient" not in content
        assert "complete_json" not in content

    def test_does_not_import_keynote(self):
        import open_keynote_agent.images.planner as planner_mod
        source = planner_mod.__file__
        assert source is not None
        content = Path(source).read_text()
        assert "tools.keynote" not in content
        assert "OsascriptRunner" not in content


# ---------------------------------------------------------------------------
# FakeImageProvider
# ---------------------------------------------------------------------------

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class TestFakeImageProvider:
    def test_generates_file(self, tmp_path: Path):
        provider = FakeImageProvider()
        out = tmp_path / "slide_01.png"
        provider.generate(ImageSpec(prompt="test"), out)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_generates_valid_png_signature(self, tmp_path: Path):
        provider = FakeImageProvider()
        out = tmp_path / "slide_01.png"
        provider.generate(ImageSpec(prompt="test"), out)
        assert out.read_bytes()[:8] == _PNG_SIGNATURE

    def test_name_is_fake(self):
        assert FakeImageProvider().name == "fake"

    def test_no_network_required(self, tmp_path: Path):
        # Passes if it completes without network calls (no mock needed)
        provider = FakeImageProvider()
        out = tmp_path / "slide_01.png"
        provider.generate(ImageSpec(prompt="no network"), out)
        assert out.exists()


# ---------------------------------------------------------------------------
# Provider loader
# ---------------------------------------------------------------------------

class TestLoadImageProviderFromEnv:
    def test_default_is_fake(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("OKA_IMAGE_PROVIDER", raising=False)
        p = load_image_provider_from_env()
        assert isinstance(p, FakeImageProvider)

    def test_fake_explicit(self):
        p = load_image_provider_from_env("fake")
        assert isinstance(p, FakeImageProvider)

    def test_unknown_provider_raises(self):
        with pytest.raises(UnsupportedImageProviderError):
            load_image_provider_from_env("not_a_real_provider")

    def test_bedrock_without_model_id_raises(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("OKA_IMAGE_MODEL", raising=False)
        with pytest.raises(ValueError, match="OKA_IMAGE_MODEL"):
            load_image_provider_from_env("bedrock")

    def test_env_var_selects_fake(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("OKA_IMAGE_PROVIDER", "fake")
        p = load_image_provider_from_env()
        assert isinstance(p, FakeImageProvider)


# ---------------------------------------------------------------------------
# Prompt hash
# ---------------------------------------------------------------------------

class TestPromptHash:
    def test_returns_16_hex_chars(self):
        art_spec = SlideArtSpec(
            slide_index=1,
            slide_title="Cover",
            image=ImageSpec(prompt="test"),
        )
        h = _prompt_hash(art_spec, "fake")
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic(self):
        art_spec = SlideArtSpec(
            slide_index=1,
            slide_title="Cover",
            image=ImageSpec(prompt="test"),
        )
        assert _prompt_hash(art_spec, "fake") == _prompt_hash(art_spec, "fake")

    def test_different_prompt_different_hash(self):
        a = SlideArtSpec(slide_index=1, slide_title="x", image=ImageSpec(prompt="aaa"))
        b = SlideArtSpec(slide_index=1, slide_title="x", image=ImageSpec(prompt="bbb"))
        assert _prompt_hash(a, "fake") != _prompt_hash(b, "fake")

    def test_different_provider_different_hash(self):
        spec = SlideArtSpec(slide_index=1, slide_title="x", image=ImageSpec(prompt="aaa"))
        assert _prompt_hash(spec, "fake") != _prompt_hash(spec, "bedrock")

    def test_matches_documented_formula(self):
        spec = SlideArtSpec(
            slide_index=1,
            slide_title="Cover",
            image=ImageSpec(prompt="test", seed=42),
        )
        canonical = json.dumps(
            spec.image.model_dump(mode="json"),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        expected = hashlib.sha256(f"fake\n{canonical}".encode("utf-8")).hexdigest()[:16]
        assert _prompt_hash(spec, "fake") == expected


# ---------------------------------------------------------------------------
# generate_image_assets
# ---------------------------------------------------------------------------

class TestGenerateImageAssets:
    def test_creates_assets_dir(self, tmp_path: Path):
        deck = _three_pigs_deck()
        generate_image_assets(deck, FakeImageProvider(), output_dir=tmp_path)
        assert (tmp_path / "assets").is_dir()

    def test_one_png_per_slide(self, tmp_path: Path):
        deck = _three_pigs_deck()
        generate_image_assets(deck, FakeImageProvider(), output_dir=tmp_path)
        pngs = sorted((tmp_path / "assets").glob("*.png"))
        assert len(pngs) == len(deck.slides)

    def test_png_files_have_valid_signature(self, tmp_path: Path):
        deck = _three_pigs_deck()
        generate_image_assets(deck, FakeImageProvider(), output_dir=tmp_path)
        for png in (tmp_path / "assets").glob("*.png"):
            assert png.read_bytes()[:8] == _PNG_SIGNATURE

    def test_writes_image_manifest_json(self, tmp_path: Path):
        deck = _three_pigs_deck()
        generate_image_assets(deck, FakeImageProvider(), output_dir=tmp_path)
        assert (tmp_path / "image_manifest.json").exists()

    def test_manifest_deck_title(self, tmp_path: Path):
        deck = _three_pigs_deck()
        manifest = generate_image_assets(deck, FakeImageProvider(), output_dir=tmp_path)
        assert manifest.deck_title == deck.title

    def test_manifest_provider(self, tmp_path: Path):
        deck = _three_pigs_deck()
        manifest = generate_image_assets(deck, FakeImageProvider(), output_dir=tmp_path)
        assert manifest.provider == "fake"

    def test_manifest_has_one_asset_per_slide(self, tmp_path: Path):
        deck = _three_pigs_deck()
        manifest = generate_image_assets(deck, FakeImageProvider(), output_dir=tmp_path)
        assert len(manifest.assets) == len(deck.slides)

    def test_manifest_assets_not_cached_on_first_run(self, tmp_path: Path):
        deck = _three_pigs_deck()
        manifest = generate_image_assets(deck, FakeImageProvider(), output_dir=tmp_path)
        assert all(not a.cached for a in manifest.assets)

    def test_writes_art_spec_json(self, tmp_path: Path):
        deck = _three_pigs_deck()
        generate_image_assets(deck, FakeImageProvider(), output_dir=tmp_path)
        art_path = tmp_path / "art_spec.json"
        assert art_path.exists()
        data = json.loads(art_path.read_text())
        assert isinstance(data, dict)
        assert data["deck_title"] == deck.title
        assert len(data["slides"]) == len(deck.slides)

    def test_art_spec_json_contains_prompts(self, tmp_path: Path):
        deck = _three_pigs_deck()
        generate_image_assets(deck, FakeImageProvider(), output_dir=tmp_path)
        data = json.loads((tmp_path / "art_spec.json").read_text())
        assert "deck_title" in data
        assert "slides" in data
        for entry in data["slides"]:
            assert "image" in entry
            assert "prompt" in entry["image"]

    def test_assets_relative_paths_in_manifest(self, tmp_path: Path):
        deck = _three_pigs_deck()
        manifest = generate_image_assets(deck, FakeImageProvider(), output_dir=tmp_path)
        for asset in manifest.assets:
            # path must be relative (joinable against output_dir)
            assert not Path(asset.path).is_absolute()
            assert (tmp_path / asset.path).exists()

    def _counting_provider(self) -> tuple[FakeImageProvider, list[int]]:
        provider = FakeImageProvider()
        calls: list[int] = []
        original = provider.generate

        def counting_generate(spec, path):
            calls.append(1)
            return original(spec, path)

        provider.generate = counting_generate  # type: ignore[method-assign]
        return provider, calls

    def test_cache_hit_via_shared_cache(self, tmp_path: Path):
        """Second run in a different output_dir hits shared cache."""
        deck = _three_pigs_deck()
        cache_dir = tmp_path / "cache"
        out1 = tmp_path / "run1"
        out2 = tmp_path / "run2"
        generate_image_assets(deck, FakeImageProvider(), output_dir=out1, cache_dir=cache_dir)

        provider, calls = self._counting_provider()
        manifest2 = generate_image_assets(deck, provider, output_dir=out2, cache_dir=cache_dir)
        assert calls == []
        assert all(a.cached for a in manifest2.assets)

    def test_cache_hit_on_second_run_same_dir(self, tmp_path: Path):
        deck = _three_pigs_deck()
        cache_dir = tmp_path / "cache"
        generate_image_assets(deck, FakeImageProvider(), output_dir=tmp_path, cache_dir=cache_dir)

        provider, calls = self._counting_provider()
        manifest2 = generate_image_assets(deck, provider, output_dir=tmp_path, cache_dir=cache_dir)
        assert calls == []
        assert all(a.cached for a in manifest2.assets)

    def test_changed_prompt_invalidates_cache(self, tmp_path: Path):
        deck = _three_pigs_deck()
        cache_dir = tmp_path / "cache"
        generate_image_assets(deck, FakeImageProvider(), output_dir=tmp_path, cache_dir=cache_dir)

        raw = _minimal_deck_dict(n_slides=4)
        raw["slides"][0]["visual"]["description"] = "COMPLETELY DIFFERENT SCENE"
        deck2 = DeckSpec(**raw)

        provider, calls = self._counting_provider()
        generate_image_assets(deck2, provider, output_dir=tmp_path, cache_dir=cache_dir)
        assert len(calls) >= 1

    def test_force_regenerates_all(self, tmp_path: Path):
        deck = _three_pigs_deck()
        cache_dir = tmp_path / "cache"
        generate_image_assets(deck, FakeImageProvider(), output_dir=tmp_path, cache_dir=cache_dir)

        provider, calls = self._counting_provider()
        generate_image_assets(deck, provider, output_dir=tmp_path, force=True, cache_dir=cache_dir)
        assert len(calls) == len(deck.slides)

    def test_manifest_assets_dir_is_relative(self, tmp_path: Path):
        deck = _three_pigs_deck()
        manifest = generate_image_assets(deck, FakeImageProvider(), output_dir=tmp_path)
        assert not Path(manifest.assets_dir).is_absolute()

    def test_does_not_write_outside_output_dir(self, tmp_path: Path):
        deck = _three_pigs_deck()
        generate_image_assets(deck, FakeImageProvider(), output_dir=tmp_path)
        # Only tmp_path and its children should have been written
        other = tmp_path.parent / "should_not_exist.png"
        assert not other.exists()


# ---------------------------------------------------------------------------
# CLI: generate-images
# ---------------------------------------------------------------------------

class TestGenerateImagesCLI:
    def test_writes_assets_and_manifest(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        spec_path = _write_deck_spec(tmp_path)
        out = tmp_path / "out"
        result = cli_runner.invoke(app, [
            "generate-images", str(spec_path), "--output", str(out), "--provider", "fake",
        ])
        assert result.exit_code == 0
        assert (out / "image_manifest.json").exists()
        assert (out / "assets").is_dir()
        assert len(list((out / "assets").glob("*.png"))) == 3

    def test_writes_art_spec_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        spec_path = _write_deck_spec(tmp_path)
        out = tmp_path / "out"
        cli_runner.invoke(app, [
            "generate-images", str(spec_path), "--output", str(out), "--provider", "fake",
        ])
        assert (out / "art_spec.json").exists()

    def test_missing_file_exits_nonzero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        result = cli_runner.invoke(app, [
            "generate-images", str(tmp_path / "missing.json"),
        ])
        assert result.exit_code != 0

    def test_invalid_deck_spec_exits_nonzero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        bad = tmp_path / "bad.json"
        bad.write_text('{"not": "a deck"}', encoding="utf-8")
        result = cli_runner.invoke(app, [
            "generate-images", str(bad), "--output", str(tmp_path / "out"),
        ])
        assert result.exit_code != 0

    def test_unknown_provider_exits_nonzero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        spec_path = _write_deck_spec(tmp_path)
        result = cli_runner.invoke(app, [
            "generate-images", str(spec_path), "--provider", "not_real",
        ])
        assert result.exit_code != 0

    def test_default_output_dir_under_runs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        spec_path = _write_deck_spec(tmp_path)
        cli_runner.invoke(app, [
            "generate-images", str(spec_path), "--provider", "fake",
        ])
        runs_dirs = list((tmp_path / ".runs").glob("*-images*"))
        assert len(runs_dirs) >= 1

    def test_default_dir_cleaned_on_invalid_deck(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        bad = tmp_path / "bad.json"
        bad.write_text('{"not": "a deck"}', encoding="utf-8")
        cli_runner.invoke(app, ["generate-images", str(bad), "--provider", "fake"])
        runs = tmp_path / ".runs"
        if runs.exists():
            dirs = list(runs.glob("*-images*"))
            assert dirs == []

    def test_force_flag_accepted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        spec_path = _write_deck_spec(tmp_path)
        out = tmp_path / "out"
        result = cli_runner.invoke(app, [
            "generate-images", str(spec_path), "--output", str(out),
            "--provider", "fake", "--force",
        ])
        assert result.exit_code == 0

    def test_prints_asset_and_manifest_paths(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        spec_path = _write_deck_spec(tmp_path)
        out = tmp_path / "out"
        result = cli_runner.invoke(app, [
            "generate-images", str(spec_path), "--output", str(out), "--provider", "fake",
        ])
        assert "assets" in result.output
        assert "manifest" in result.output.lower() or "image_manifest" in result.output

    def test_does_not_call_keynote(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        spec_path = _write_deck_spec(tmp_path)
        out = tmp_path / "out"
        called = []
        monkeypatch.setattr(cli_module, "register_keynote_tools", lambda *a, **kw: called.append(1))
        cli_runner.invoke(app, [
            "generate-images", str(spec_path), "--output", str(out), "--provider", "fake",
        ])
        assert called == []

    def test_does_not_call_llm(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        spec_path = _write_deck_spec(tmp_path)
        out = tmp_path / "out"
        called = []
        monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: called.append(1) or MagicMock())
        cli_runner.invoke(app, [
            "generate-images", str(spec_path), "--output", str(out), "--provider", "fake",
        ])
        assert called == []

    def test_force_regenerates_via_cli(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        spec_path = _write_deck_spec(tmp_path)
        out = tmp_path / "out"
        # First run (uses default shared cache under .runs/image-cache/)
        cli_runner.invoke(app, [
            "generate-images", str(spec_path), "--output", str(out), "--provider", "fake",
        ])
        # Second run with --force — all assets regenerated regardless of cache
        result = cli_runner.invoke(app, [
            "generate-images", str(spec_path), "--output", str(out),
            "--provider", "fake", "--force",
        ])
        assert result.exit_code == 0
        manifest = ImageManifest.model_validate_json(
            (out / "image_manifest.json").read_text()
        )
        assert all(not a.cached for a in manifest.assets)
