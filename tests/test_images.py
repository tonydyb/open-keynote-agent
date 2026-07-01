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
from open_keynote_agent.images.generator import _prompt_hash, generate_image_assets, parse_slide_selector
from open_keynote_agent.images.planner import _NO_TEXT_INSTRUCTION, build_slide_art_specs
from open_keynote_agent.images.provider import (
    BedrockImageProvider,
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
# Slide selector parsing
# ---------------------------------------------------------------------------

class TestParseSlideSelector:
    def test_single_indexes(self):
        assert parse_slide_selector("1,4,9") == {1, 4, 9}

    def test_ranges(self):
        assert parse_slide_selector("1-3,5") == {1, 2, 3, 5}

    def test_strips_spaces_and_deduplicates(self):
        assert parse_slide_selector(" 1, 2-3, 3 ") == {1, 2, 3}

    @pytest.mark.parametrize("value", ["", " ", "1,,2", "a", "3-1", "0", "-1", "1-", "1-2-3"])
    def test_invalid_selector_raises(self, value: str):
        with pytest.raises(ValueError):
            parse_slide_selector(value)


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
        assert spec.style == "deck-specified"
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

    def test_can_filter_selected_slides(self):
        deck = _three_pigs_deck()
        specs = build_slide_art_specs(deck, slide_indexes={1, 4})
        assert [s.slide_index for s in specs] == [1, 4]

    def test_filter_rejects_missing_slide(self):
        deck = _three_pigs_deck()
        with pytest.raises(ValueError, match="slide 99 does not exist"):
            build_slide_art_specs(deck, slide_indexes={99})

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

    def test_prompt_contains_mood_in_deck_style_mode(self):
        # deck_style mode uses DeckSpec.style.mood; fixed presets do not.
        deck = _three_pigs_deck()
        specs = build_slide_art_specs(deck, style_mode="deck_style")
        for spec in specs:
            assert deck.style.mood in spec.image.prompt

    def test_default_mode_does_not_include_deck_mood(self):
        # Default (soft_storybook_watercolor) uses preset, not deck mood text.
        raw = _minimal_deck_dict(n_slides=1)
        raw["style"]["mood"] = "flat vector paper-cut collage"
        deck = DeckSpec(**raw)
        spec = build_slide_art_specs(deck)[0]
        assert "flat vector paper-cut collage" not in spec.image.prompt

    def test_prompt_contains_audience(self):
        # Audience is included even in fixed preset modes.
        deck = _three_pigs_deck()
        specs = build_slide_art_specs(deck)
        for spec in specs:
            assert "children" in spec.image.prompt

    def test_prompt_contains_typography_in_deck_style_mode(self):
        raw = _minimal_deck_dict(n_slides=1)
        raw["style"]["typography"] = "bold comic lettering"
        deck = DeckSpec(**raw)
        spec = build_slide_art_specs(deck, style_mode="deck_style")[0]
        assert "typography: bold comic lettering" in spec.image.prompt

    def test_prompt_does_not_inject_styles_outside_selected_mode(self):
        # Using deck_style: deck mood appears, preset keywords must not appear.
        raw = _minimal_deck_dict(n_slides=1)
        raw["style"]["mood"] = "flat vector paper-cut collage"
        deck = DeckSpec(**raw)
        spec = build_slide_art_specs(deck, style_mode="deck_style")[0]
        prompt_lower = spec.image.prompt.lower()
        assert "flat vector paper-cut collage" in prompt_lower
        # Preset descriptions must not be mixed in when deck_style is selected.
        assert "soft_storybook_watercolor" not in prompt_lower
        assert "cute_hand_drawn_cartoon" not in prompt_lower
        assert "paper_cut_collage_storybook" not in prompt_lower

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
        # Emoji-derived words appear as required subjects in the 011 director format.
        assert "- pig" in specs[0].image.prompt
        assert "- house" in specs[0].image.prompt

    def test_prompt_supports_arbitrary_story_titles(self):
        # 011 director: deck title appears in "Story context:" section (after primary scene).
        raw = _minimal_deck_dict(n_slides=1)
        raw["title"] = "Snow White"
        raw["subtitle"] = "A fairy tale about kindness"
        raw["slides"][0]["title"] = "The Magic Mirror"
        raw["slides"][0]["visual"]["description"] = "Snow White in an enchanted forest"
        raw["slides"][0]["visual"]["emoji"] = ["👸", "🪞", "🍎"]
        deck = DeckSpec(**raw)

        spec = build_slide_art_specs(deck)[0]

        # Primary scene must appear before story context
        primary_scene_pos = spec.image.prompt.find("Primary scene, follow exactly:")
        story_context_pos = spec.image.prompt.find("Story context:")
        assert primary_scene_pos != -1
        assert story_context_pos != -1
        assert primary_scene_pos < story_context_pos

        # Deck title is in the story context section
        assert "Snow White" in spec.image.prompt
        assert "A fairy tale about kindness" in spec.image.prompt

        # Slide content appears in primary scene
        assert "The Magic Mirror" in spec.image.prompt
        assert "Snow White in an enchanted forest" in spec.image.prompt

        # Emoji-derived words appear as required subjects
        assert "- princess" in spec.image.prompt
        assert "- magic mirror" in spec.image.prompt
        assert "- apple" in spec.image.prompt

    def test_prompt_supports_non_english_arbitrary_story_titles(self):
        # 011 director: deck title in "Story context:" section (after primary scene).
        raw = _minimal_deck_dict(n_slides=1)
        raw["title"] = "冰雪奇缘"
        raw["slides"][0]["title"] = "冰雪城堡"
        raw["slides"][0]["visual"]["description"] = "女王在冰雪城堡中释放魔法"
        raw["slides"][0]["visual"]["emoji"] = ["❄️", "🏰", "👑"]
        deck = DeckSpec(**raw)

        spec = build_slide_art_specs(deck)[0]

        # Deck title in story context after primary scene
        primary_scene_pos = spec.image.prompt.find("Primary scene, follow exactly:")
        story_context_pos = spec.image.prompt.find("Story context:")
        assert primary_scene_pos < story_context_pos
        assert "冰雪奇缘" in spec.image.prompt

        # Slide content in primary scene
        assert "冰雪城堡" in spec.image.prompt
        assert "女王在冰雪城堡中释放魔法" in spec.image.prompt

        # Emoji-derived required subjects
        assert "- snowflake" in spec.image.prompt
        assert "- castle" in spec.image.prompt
        assert "- crown" in spec.image.prompt

    def test_prompt_contains_generic_story_match_instruction(self):
        # 011 director: story context section includes background context instruction.
        deck = _three_pigs_deck()
        spec = build_slide_art_specs(deck)[0]
        assert "background context" in spec.image.prompt
        assert "do not add unrelated story elements" in spec.image.prompt

    def test_prompt_planner_has_no_story_specific_anchor(self):
        import open_keynote_agent.images.planner as planner_mod
        source = planner_mod.__file__
        assert source is not None
        content = Path(source).read_text()
        assert "_three_pigs_anchor" not in content
        assert "piglet brothers" not in content

    def test_negative_prompt_is_generic_and_allows_humans(self):
        # 011 director: generic text/UI exclusions; no hardcoded human/animal bans.
        deck = _three_pigs_deck()
        spec = build_slide_art_specs(deck)[0]
        assert spec.image.negative_prompt is not None
        assert "watermark" in spec.image.negative_prompt
        assert "document" in spec.image.negative_prompt
        assert "human children" not in spec.image.negative_prompt
        assert "animals" not in spec.image.negative_prompt

    def test_style_avoid_terms_are_in_negative_prompt(self):
        raw = _minimal_deck_dict(n_slides=1)
        raw["style"]["avoid"] = ["watercolor", "soft lighting"]
        deck = DeckSpec(**raw)
        spec = build_slide_art_specs(deck)[0]
        assert spec.image.negative_prompt is not None
        assert "watercolor" in spec.image.negative_prompt
        assert "soft lighting" in spec.image.negative_prompt

    def test_prompt_contains_palette_in_deck_style_mode(self):
        deck = _three_pigs_deck()
        specs = build_slide_art_specs(deck, style_mode="deck_style")
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
# Bedrock image provider
# ---------------------------------------------------------------------------

class TestBedrockImageProvider:
    def test_stability_request_body(self):
        provider = BedrockImageProvider("stability.stable-image-core-v1:1")

        body = provider._build_request_body(ImageSpec(
            prompt="storybook pigs",
            negative_prompt="text",
            seed=123,
        ))

        assert body == {
            "prompt": "storybook pigs",
            "mode": "text-to-image",
            "aspect_ratio": "16:9",
            "output_format": "png",
            "negative_prompt": "text",
            "seed": 123,
        }

    def test_amazon_request_body(self):
        provider = BedrockImageProvider("amazon.titan-image-generator-v2:0")

        body = provider._build_request_body(ImageSpec(
            prompt="storybook pigs",
            negative_prompt="text",
            seed=123,
        ))

        assert body["taskType"] == "TEXT_IMAGE"
        assert body["textToImageParams"] == {
            "text": "storybook pigs",
            "negativeText": "text",
        }
        assert body["imageGenerationConfig"]["seed"] == 123
        assert body["imageGenerationConfig"]["width"] == 1280
        assert body["imageGenerationConfig"]["height"] == 720


# ---------------------------------------------------------------------------
# Provider loader
# ---------------------------------------------------------------------------

class TestLoadImageProviderFromEnv:
    def test_default_is_fake(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("OMA_SKIP_DOTENV", "1")
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
        monkeypatch.setenv("OMA_SKIP_DOTENV", "1")
        monkeypatch.delenv("OKA_IMAGE_MODEL", raising=False)
        with pytest.raises(ValueError, match="OKA_IMAGE_MODEL"):
            load_image_provider_from_env("bedrock")

    def test_env_var_selects_fake(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("OMA_SKIP_DOTENV", "1")
        monkeypatch.setenv("OKA_IMAGE_PROVIDER", "fake")
        p = load_image_provider_from_env()
        assert isinstance(p, FakeImageProvider)

    def test_loads_bedrock_config_from_dotenv(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OMA_SKIP_DOTENV", raising=False)
        monkeypatch.delenv("OKA_IMAGE_PROVIDER", raising=False)
        monkeypatch.delenv("OKA_IMAGE_MODEL", raising=False)
        monkeypatch.delenv("OKA_IMAGE_AWS_REGION", raising=False)
        monkeypatch.delenv("AWS_REGION", raising=False)
        monkeypatch.delenv("AWS_PROFILE", raising=False)
        (tmp_path / ".env").write_text(
            "\n".join([
                "OKA_IMAGE_MODEL=amazon.nova-canvas-v1:0",
                "AWS_REGION=us-east-1",
                "OKA_IMAGE_AWS_REGION=us-west-2",
                "AWS_PROFILE=storybook-test",
            ]),
            encoding="utf-8",
        )

        p = load_image_provider_from_env("bedrock")

        assert isinstance(p, BedrockImageProvider)
        assert p.model_id == "amazon.nova-canvas-v1:0"
        assert p.region == "us-west-2"
        assert p.profile == "storybook-test"

    def test_bedrock_region_falls_back_to_aws_region(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("OMA_SKIP_DOTENV", "1")
        monkeypatch.setenv("OKA_IMAGE_MODEL", "stability.stable-image-core-v1:1")
        monkeypatch.delenv("OKA_IMAGE_AWS_REGION", raising=False)
        monkeypatch.setenv("AWS_REGION", "us-east-1")

        p = load_image_provider_from_env("bedrock")

        assert isinstance(p, BedrockImageProvider)
        assert p.region == "us-east-1"

    def test_skip_dotenv_for_image_provider(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("OMA_SKIP_DOTENV", "1")
        monkeypatch.delenv("OKA_IMAGE_MODEL", raising=False)
        (tmp_path / ".env").write_text(
            "OKA_IMAGE_MODEL=amazon.nova-canvas-v1:0\n",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="OKA_IMAGE_MODEL"):
            load_image_provider_from_env("bedrock")


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

    def test_generates_only_selected_slides(self, tmp_path: Path):
        deck = _three_pigs_deck()
        manifest = generate_image_assets(
            deck,
            FakeImageProvider(),
            output_dir=tmp_path,
            slide_indexes={1, 4},
        )

        assert sorted(p.name for p in (tmp_path / "assets").glob("*.png")) == [
            "slide_01.png",
            "slide_04.png",
        ]
        assert [a.slide_index for a in manifest.assets] == [1, 4]

        art_spec = json.loads((tmp_path / "art_spec.json").read_text())
        assert [s["slide_index"] for s in art_spec["slides"]] == [1, 4]

    def test_selected_missing_slide_raises(self, tmp_path: Path):
        deck = _three_pigs_deck()
        with pytest.raises(ValueError, match="slide 99 does not exist"):
            generate_image_assets(
                deck,
                FakeImageProvider(),
                output_dir=tmp_path,
                slide_indexes={99},
            )

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

    def test_art_spec_from_english_source_deck_uses_english_visual_prompt(self, tmp_path: Path):
        raw = _minimal_deck_dict(n_slides=1)
        raw["title"] = "The Three Little Pigs"
        raw["language"] = "en"
        raw["content_language"] = "en"
        raw["slides"][0]["title"] = "Cover"
        raw["slides"][0]["visual"]["description"] = (
            "Three cute pink anthropomorphic piglets standing in front of a brick cottage"
        )
        deck = DeckSpec(**raw)

        generate_image_assets(deck, FakeImageProvider(), output_dir=tmp_path)

        data = json.loads((tmp_path / "art_spec.json").read_text())
        prompt = data["slides"][0]["image"]["prompt"]
        assert "The Three Little Pigs" in prompt
        assert "Three cute pink anthropomorphic piglets" in prompt
        assert "三只小猪" not in prompt

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

    def test_slides_option_generates_selected_assets(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        spec_path = _write_deck_spec(tmp_path, n_slides=5)
        out = tmp_path / "out"
        result = cli_runner.invoke(app, [
            "generate-images", str(spec_path), "--output", str(out),
            "--provider", "fake", "--slides", "1,4-5",
        ])
        assert result.exit_code == 0
        assert sorted(p.name for p in (out / "assets").glob("*.png")) == [
            "slide_01.png",
            "slide_04.png",
            "slide_05.png",
        ]

        manifest = ImageManifest.model_validate_json(
            (out / "image_manifest.json").read_text()
        )
        assert [a.slide_index for a in manifest.assets] == [1, 4, 5]

        art_spec = json.loads((out / "art_spec.json").read_text())
        assert [s["slide_index"] for s in art_spec["slides"]] == [1, 4, 5]

    def test_slides_option_rejects_missing_slide(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        spec_path = _write_deck_spec(tmp_path, n_slides=3)
        result = cli_runner.invoke(app, [
            "generate-images", str(spec_path), "--provider", "fake", "--slides", "99",
        ])
        assert result.exit_code != 0
        assert "slide 99 does not exist" in result.output

    def test_slides_option_rejects_invalid_selector(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        spec_path = _write_deck_spec(tmp_path)
        result = cli_runner.invoke(app, [
            "generate-images", str(spec_path), "--provider", "fake", "--slides", "3-1",
        ])
        assert result.exit_code != 0
        assert "invalid slide range" in result.output

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


# ---------------------------------------------------------------------------
# DirectedImagePrompt model (change 011)
# ---------------------------------------------------------------------------

class TestDirectedImagePrompt:
    from open_keynote_agent.images.director import DirectedImagePrompt

    def _valid_kwargs(self) -> dict:
        return {
            "slide_index": 1,
            "slide_title": "Cover",
            "primary_scene": "Three pigs outside their houses",
            "prompt": "Primary scene: Three pigs outside their houses\n\nNo text.",
        }

    def test_valid_minimal(self):
        from open_keynote_agent.images.director import DirectedImagePrompt
        d = DirectedImagePrompt(**self._valid_kwargs())
        assert d.slide_index == 1
        assert d.slide_title == "Cover"
        assert d.primary_scene == "Three pigs outside their houses"
        assert d.required_subjects == []
        assert d.forbidden_subjects == []
        assert d.composition is None
        assert d.style_notes == []
        assert d.story_context is None
        assert d.negative_prompt is None

    def test_slide_index_ge_one(self):
        from open_keynote_agent.images.director import DirectedImagePrompt
        from pydantic import ValidationError
        kw = self._valid_kwargs()
        kw["slide_index"] = 0
        with pytest.raises(ValidationError):
            DirectedImagePrompt(**kw)

    def test_blank_slide_title_raises(self):
        from open_keynote_agent.images.director import DirectedImagePrompt
        from pydantic import ValidationError
        kw = self._valid_kwargs()
        kw["slide_title"] = "   "
        with pytest.raises(ValidationError):
            DirectedImagePrompt(**kw)

    def test_blank_primary_scene_raises(self):
        from open_keynote_agent.images.director import DirectedImagePrompt
        from pydantic import ValidationError
        kw = self._valid_kwargs()
        kw["primary_scene"] = ""
        with pytest.raises(ValidationError):
            DirectedImagePrompt(**kw)

    def test_blank_prompt_raises(self):
        from open_keynote_agent.images.director import DirectedImagePrompt
        from pydantic import ValidationError
        kw = self._valid_kwargs()
        kw["prompt"] = "  "
        with pytest.raises(ValidationError):
            DirectedImagePrompt(**kw)

    def test_empty_string_in_required_subjects_raises(self):
        from open_keynote_agent.images.director import DirectedImagePrompt
        from pydantic import ValidationError
        kw = self._valid_kwargs()
        kw["required_subjects"] = ["pig", ""]
        with pytest.raises(ValidationError):
            DirectedImagePrompt(**kw)

    def test_empty_string_in_forbidden_subjects_raises(self):
        from open_keynote_agent.images.director import DirectedImagePrompt
        from pydantic import ValidationError
        kw = self._valid_kwargs()
        kw["forbidden_subjects"] = ["watermark", ""]
        with pytest.raises(ValidationError):
            DirectedImagePrompt(**kw)

    def test_extra_field_forbidden(self):
        from open_keynote_agent.images.director import DirectedImagePrompt
        from pydantic import ValidationError
        kw = self._valid_kwargs()
        kw["unknown"] = "oops"
        with pytest.raises(ValidationError):
            DirectedImagePrompt(**kw)

    def test_optional_fields_accepted(self):
        from open_keynote_agent.images.director import DirectedImagePrompt
        d = DirectedImagePrompt(
            slide_index=2,
            slide_title="The Wolf",
            primary_scene="A big bad wolf huffing at a straw house",
            required_subjects=["wolf", "straw house"],
            forbidden_subjects=["watermark"],
            composition="medium-wide storybook scene",
            style_notes=["warm and cheerful"],
            story_context="Three Little Pigs",
            prompt="Primary scene: A big bad wolf.\n\nNo text.",
            negative_prompt="watermark, text",
        )
        assert d.required_subjects == ["wolf", "straw house"]
        assert d.story_context == "Three Little Pigs"
        assert d.composition == "medium-wide storybook scene"


# ---------------------------------------------------------------------------
# build_directed_image_prompt (change 011)
# ---------------------------------------------------------------------------

class TestBuildDirectedImagePrompt:
    def _snow_white_deck(self) -> DeckSpec:
        return DeckSpec(**{
            "title": "Snow White",
            "subtitle": "A fairy tale about kindness",
            "style": {"mood": "magical storybook", "audience": "children"},
            "slides": [{
                "index": 1,
                "kind": "chapter",
                "title": "The Evil Queen",
                "visual": {
                    "description": "An evil queen in a dark royal chamber stands before a glowing magic mirror",
                    "emoji": ["👑", "🪞"],
                },
            }],
        })

    def _three_pigs_deck_with_cover(self) -> DeckSpec:
        raw = _minimal_deck_dict(n_slides=1)
        raw["slides"][0]["kind"] = "cover"
        return DeckSpec(**raw)

    def test_returns_directed_image_prompt(self):
        from open_keynote_agent.images.director import build_directed_image_prompt, DirectedImagePrompt
        deck = self._snow_white_deck()
        d = build_directed_image_prompt(deck, deck.slides[0])
        assert isinstance(d, DirectedImagePrompt)

    def test_slide_index_matches(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._snow_white_deck()
        d = build_directed_image_prompt(deck, deck.slides[0])
        assert d.slide_index == 1

    def test_slide_title_matches(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._snow_white_deck()
        d = build_directed_image_prompt(deck, deck.slides[0])
        assert d.slide_title == "The Evil Queen"

    def test_primary_scene_starts_with_visual_description(self):
        # P2 fix: primary_scene leads with visual.description, not slide title.
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._snow_white_deck()
        d = build_directed_image_prompt(deck, deck.slides[0])
        assert d.primary_scene.startswith("An evil queen in a dark royal chamber")

    def test_primary_scene_contains_slide_title_as_label(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._snow_white_deck()
        d = build_directed_image_prompt(deck, deck.slides[0])
        assert "The Evil Queen" in d.primary_scene

    def test_primary_scene_contains_visual_description(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._snow_white_deck()
        d = build_directed_image_prompt(deck, deck.slides[0])
        assert "evil queen" in d.primary_scene.lower()
        assert "magic mirror" in d.primary_scene.lower()

    def test_deck_style_prompt_starts_with_primary_scene_section(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._snow_white_deck()
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="deck_style")
        assert d.prompt.startswith("Primary scene, follow exactly:")

    def test_fixed_preset_prompt_starts_with_style_anchor(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._snow_white_deck()
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="paper_cut_collage_storybook")
        assert d.prompt.startswith("Image style, follow strongly:")
        assert "paper_cut_collage_storybook" in d.prompt.split("\n\n", 1)[0]

    def test_story_context_after_primary_scene_in_prompt(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._snow_white_deck()
        d = build_directed_image_prompt(deck, deck.slides[0])
        primary_pos = d.prompt.find("Primary scene, follow exactly:")
        story_pos = d.prompt.find("Story context:")
        assert primary_pos != -1
        assert story_pos != -1
        assert primary_pos < story_pos

    def test_story_context_field_contains_deck_title(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._snow_white_deck()
        d = build_directed_image_prompt(deck, deck.slides[0])
        assert d.story_context is not None
        assert "Snow White" in d.story_context

    def test_story_context_contains_subtitle_when_present(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._snow_white_deck()
        d = build_directed_image_prompt(deck, deck.slides[0])
        assert d.story_context is not None
        assert "A fairy tale about kindness" in d.story_context

    def test_prompt_does_not_start_with_deck_title(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._snow_white_deck()
        d = build_directed_image_prompt(deck, deck.slides[0])
        assert not d.prompt.startswith("Snow White")

    def test_required_subjects_from_emoji(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._snow_white_deck()
        d = build_directed_image_prompt(deck, deck.slides[0])
        # 👑 → crown, 🪞 → magic mirror
        assert "crown" in d.required_subjects
        assert "magic mirror" in d.required_subjects

    def test_required_subjects_in_prompt(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._snow_white_deck()
        d = build_directed_image_prompt(deck, deck.slides[0])
        if d.required_subjects:
            assert "Required subjects:" in d.prompt
            for subj in d.required_subjects:
                assert f"- {subj}" in d.prompt

    def test_generic_forbidden_subjects_in_negative_prompt(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._snow_white_deck()
        d = build_directed_image_prompt(deck, deck.slides[0])
        assert d.negative_prompt is not None
        for term in ("text", "watermark", "logo", "document", "poster"):
            assert term in d.negative_prompt

    def test_style_avoid_in_negative_prompt(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        raw = _minimal_deck_dict(n_slides=1)
        raw["style"]["avoid"] = ["photorealistic", "gore"]
        deck = DeckSpec(**raw)
        d = build_directed_image_prompt(deck, deck.slides[0])
        assert d.negative_prompt is not None
        assert "photorealistic" in d.negative_prompt
        assert "gore" in d.negative_prompt

    def test_no_fixed_art_styles_injected_outside_selected_mode(self):
        # deck_style mode: no preset descriptions should appear in prompt.
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._snow_white_deck()
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="deck_style")
        prompt_lower = d.prompt.lower()
        for term in ("oil painting", "soft lighting", "warm picture book",
                     "paper-cut", "hand-drawn cartoon"):
            assert term not in prompt_lower, f"Unexpected style term injected: {term!r}"

    def test_style_notes_for_deck_style_use_deck_fields(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._snow_white_deck()
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="deck_style")
        # Style section should contain mood and audience from DeckSpec
        assert any("magical storybook" in note for note in d.style_notes)
        assert any("children" in note for note in d.style_notes)

    def test_fixed_preset_style_notes_use_preset_not_deck_mood(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._snow_white_deck()  # mood = "magical storybook"
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="soft_storybook_watercolor")
        # Preset description should appear; deck mood should not.
        assert any("soft_storybook_watercolor" in note for note in d.style_notes)
        assert not any("magical storybook" in note for note in d.style_notes)

    def test_composition_set_for_cover(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._three_pigs_deck_with_cover()
        d = build_directed_image_prompt(deck, deck.slides[0])
        assert d.composition is not None
        assert "centered" in d.composition.lower()

    def test_composition_set_for_chapter(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._snow_white_deck()
        d = build_directed_image_prompt(deck, deck.slides[0])
        assert d.composition is not None

    def test_no_text_instruction_last_in_prompt(self):
        from open_keynote_agent.images.director import build_directed_image_prompt, _NO_TEXT_INSTRUCTION
        deck = self._snow_white_deck()
        d = build_directed_image_prompt(deck, deck.slides[0])
        assert d.prompt.endswith(_NO_TEXT_INSTRUCTION)

    def test_deterministic(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._snow_white_deck()
        d1 = build_directed_image_prompt(deck, deck.slides[0])
        d2 = build_directed_image_prompt(deck, deck.slides[0])
        assert d1.prompt == d2.prompt
        assert d1.negative_prompt == d2.negative_prompt

    def test_does_not_use_story_specific_branches(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        # All three should produce valid results without hardcoded title branches
        for title in ("Snow White", "Three Little Pigs", "Frozen"):
            raw = _minimal_deck_dict(n_slides=1)
            raw["title"] = title
            deck = DeckSpec(**raw)
            d = build_directed_image_prompt(deck, deck.slides[0])
            assert d.prompt  # non-empty, no crash

    def test_humans_animals_not_globally_forbidden(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        # Use a neutral slide that won't trigger any slide-specific drift exclusions.
        raw = _minimal_deck_dict(n_slides=1)
        raw["slides"][0]["visual"]["description"] = "A happy family in a sunny meadow"
        deck = DeckSpec(**raw)
        d = build_directed_image_prompt(deck, deck.slides[0])
        neg_terms = {t.strip() for t in (d.negative_prompt or "").split(",")}
        for allowed_term in ("human", "children", "animal", "castle", "forest", "food"):
            assert allowed_term not in neg_terms, f"Globally forbidden: {allowed_term!r}"

    def test_palette_in_style_notes_in_deck_style_mode(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        raw = _minimal_deck_dict(n_slides=1)
        raw["style"]["palette"] = ["#FFE5D9", "#FFD700"]
        deck = DeckSpec(**raw)
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="deck_style")
        assert any("#FFE5D9" in note for note in d.style_notes)

    def test_typography_in_style_notes_in_deck_style_mode(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        raw = _minimal_deck_dict(n_slides=1)
        raw["style"]["typography"] = "bold comic lettering"
        deck = DeckSpec(**raw)
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="deck_style")
        assert any("bold comic lettering" in note for note in d.style_notes)

    def test_body_bullets_in_primary_scene(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        raw = _minimal_deck_dict(n_slides=1)
        raw["slides"][0]["body"] = ["Straw walls", "Muddy floor"]
        deck = DeckSpec(**raw)
        d = build_directed_image_prompt(deck, deck.slides[0])
        assert "Straw walls" in d.primary_scene
        assert "Muddy floor" in d.primary_scene

    def test_planner_uses_director_prompt(self):
        # Verify planner delegates to director — default fixed preset starts with style anchor.
        deck = _three_pigs_deck()
        specs = build_slide_art_specs(deck)
        for spec in specs:
            assert spec.image.prompt.startswith("Image style, follow strongly:")
            assert "Primary scene, follow exactly:" in spec.image.prompt


# ---------------------------------------------------------------------------
# Dry-run mode (change 011)
# ---------------------------------------------------------------------------

class TestDryRunGeneration:
    def test_dry_run_writes_art_spec_json(self, tmp_path: Path):
        from open_keynote_agent.images.generator import generate_image_assets
        deck = _three_pigs_deck()
        generate_image_assets(
            deck, FakeImageProvider(), output_dir=tmp_path, dry_run=True
        )
        assert (tmp_path / "art_spec.json").exists()

    def test_dry_run_does_not_write_manifest(self, tmp_path: Path):
        from open_keynote_agent.images.generator import generate_image_assets
        deck = _three_pigs_deck()
        generate_image_assets(
            deck, FakeImageProvider(), output_dir=tmp_path, dry_run=True
        )
        assert not (tmp_path / "image_manifest.json").exists()

    def test_dry_run_does_not_generate_pngs(self, tmp_path: Path):
        from open_keynote_agent.images.generator import generate_image_assets
        deck = _three_pigs_deck()
        generate_image_assets(
            deck, FakeImageProvider(), output_dir=tmp_path, dry_run=True
        )
        assets_dir = tmp_path / "assets"
        if assets_dir.exists():
            assert list(assets_dir.glob("*.png")) == []

    def test_dry_run_does_not_call_provider(self, tmp_path: Path):
        from open_keynote_agent.images.generator import generate_image_assets
        deck = _three_pigs_deck()
        called = []
        provider = FakeImageProvider()
        original = provider.generate

        def tracking_generate(spec, path):
            called.append(1)
            return original(spec, path)

        provider.generate = tracking_generate  # type: ignore[method-assign]
        generate_image_assets(deck, provider, output_dir=tmp_path, dry_run=True)
        assert called == []

    def test_dry_run_art_spec_json_contains_prompts(self, tmp_path: Path):
        from open_keynote_agent.images.generator import generate_image_assets
        deck = _three_pigs_deck()
        generate_image_assets(deck, FakeImageProvider(), output_dir=tmp_path, dry_run=True)
        data = json.loads((tmp_path / "art_spec.json").read_text())
        assert data["deck_title"] == deck.title
        for entry in data["slides"]:
            assert "image" in entry
            assert "prompt" in entry["image"]
            assert entry["image"]["prompt"].startswith("Image style, follow strongly:")
            assert "Primary scene, follow exactly:" in entry["image"]["prompt"]

    def test_dry_run_returns_empty_manifest(self, tmp_path: Path):
        from open_keynote_agent.images.generator import generate_image_assets
        deck = _three_pigs_deck()
        manifest = generate_image_assets(
            deck, FakeImageProvider(), output_dir=tmp_path, dry_run=True
        )
        assert manifest.assets == []
        assert manifest.deck_title == deck.title

    def test_dry_run_with_slide_filter(self, tmp_path: Path):
        from open_keynote_agent.images.generator import generate_image_assets
        deck = _three_pigs_deck()
        generate_image_assets(
            deck, FakeImageProvider(), output_dir=tmp_path,
            slide_indexes={1, 4}, dry_run=True,
        )
        data = json.loads((tmp_path / "art_spec.json").read_text())
        assert [s["slide_index"] for s in data["slides"]] == [1, 4]

    def test_dry_run_creates_output_dir_if_absent(self, tmp_path: Path):
        from open_keynote_agent.images.generator import generate_image_assets
        out = tmp_path / "new_dir"
        assert not out.exists()
        deck = _three_pigs_deck()
        generate_image_assets(deck, FakeImageProvider(), output_dir=out, dry_run=True)
        assert out.exists()
        assert (out / "art_spec.json").exists()


class TestDryRunCLI:
    def test_dry_run_writes_art_spec_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        spec_path = _write_deck_spec(tmp_path)
        out = tmp_path / "out"
        result = cli_runner.invoke(app, [
            "generate-images", str(spec_path), "--output", str(out), "--dry-run",
        ])
        assert result.exit_code == 0, result.output
        assert (out / "art_spec.json").exists()

    def test_dry_run_does_not_write_manifest(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        spec_path = _write_deck_spec(tmp_path)
        out = tmp_path / "out"
        cli_runner.invoke(app, [
            "generate-images", str(spec_path), "--output", str(out), "--dry-run",
        ])
        assert not (out / "image_manifest.json").exists()

    def test_dry_run_does_not_generate_pngs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        spec_path = _write_deck_spec(tmp_path)
        out = tmp_path / "out"
        cli_runner.invoke(app, [
            "generate-images", str(spec_path), "--output", str(out), "--dry-run",
        ])
        assets_dir = out / "assets"
        if assets_dir.exists():
            assert list(assets_dir.glob("*.png")) == []

    def test_dry_run_prints_art_spec_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        spec_path = _write_deck_spec(tmp_path)
        out = tmp_path / "out"
        result = cli_runner.invoke(app, [
            "generate-images", str(spec_path), "--output", str(out), "--dry-run",
        ])
        assert "art_spec.json" in result.output

    def test_dry_run_does_not_load_provider(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        spec_path = _write_deck_spec(tmp_path)
        out = tmp_path / "out"
        called = []
        monkeypatch.setattr(cli_module, "load_image_provider_from_env", lambda *a: called.append(1) or FakeImageProvider())
        cli_runner.invoke(app, [
            "generate-images", str(spec_path), "--output", str(out), "--dry-run",
        ])
        assert called == [], "load_image_provider_from_env should not be called in dry-run"

    def test_dry_run_with_slides_filter(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        spec_path = _write_deck_spec(tmp_path, n_slides=5)
        out = tmp_path / "out"
        result = cli_runner.invoke(app, [
            "generate-images", str(spec_path), "--output", str(out),
            "--dry-run", "--slides", "1,3",
        ])
        assert result.exit_code == 0, result.output
        data = json.loads((out / "art_spec.json").read_text())
        assert [s["slide_index"] for s in data["slides"]] == [1, 3]

    def test_dry_run_invalid_deck_exits_nonzero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        bad = tmp_path / "bad.json"
        bad.write_text('{"not": "a deck"}', encoding="utf-8")
        result = cli_runner.invoke(app, [
            "generate-images", str(bad), "--output", str(tmp_path / "out"), "--dry-run",
        ])
        assert result.exit_code != 0

    def test_dry_run_default_output_dir_under_runs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        spec_path = _write_deck_spec(tmp_path)
        cli_runner.invoke(app, ["generate-images", str(spec_path), "--dry-run"])
        runs_dirs = list((tmp_path / ".runs").glob("*-dry-run*"))
        assert len(runs_dirs) >= 1


# ---------------------------------------------------------------------------
# Style modes (change 011)
# ---------------------------------------------------------------------------

class TestStyleModes:
    """Tests for the four style mode IDs and guardrails."""

    def _deck(self) -> DeckSpec:
        raw = _minimal_deck_dict(n_slides=1)
        raw["style"]["mood"] = "custom deck mood"
        raw["style"]["audience"] = "children"
        raw["style"]["palette"] = ["#AABBCC"]
        raw["style"]["typography"] = "round serif"
        raw["slides"][0]["visual"]["decorations"] = ["glowing stars"]
        return DeckSpec(**raw)

    # --- STYLE_MODES registry ---

    def test_style_modes_registry_has_all_ids(self):
        from open_keynote_agent.images.director import STYLE_MODES
        for mode_id in ("soft_storybook_watercolor", "cute_hand_drawn_cartoon",
                        "paper_cut_collage_storybook", "deck_style"):
            assert mode_id in STYLE_MODES

    def test_default_style_mode_is_soft_storybook_watercolor(self):
        from open_keynote_agent.images.director import DEFAULT_STYLE_MODE
        assert DEFAULT_STYLE_MODE == "soft_storybook_watercolor"

    # --- Unknown style mode ---

    def test_unknown_style_mode_raises_value_error(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._deck()
        with pytest.raises(ValueError, match="unknown style mode"):
            build_directed_image_prompt(deck, deck.slides[0], style_mode="not_a_real_mode")

    def test_planner_unknown_style_mode_raises(self):
        deck = self._deck()
        with pytest.raises(ValueError, match="unknown style mode"):
            build_slide_art_specs(deck, style_mode="not_a_real_mode")

    # --- Fixed preset: soft_storybook_watercolor ---

    def test_soft_storybook_watercolor_appears_in_style_notes(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._deck()
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="soft_storybook_watercolor")
        assert any("soft_storybook_watercolor" in note for note in d.style_notes)

    def test_soft_storybook_watercolor_appears_in_prompt(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._deck()
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="soft_storybook_watercolor")
        assert "soft_storybook_watercolor" in d.prompt
        assert "watercolor texture" in d.prompt

    def test_soft_storybook_watercolor_does_not_include_deck_mood(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._deck()
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="soft_storybook_watercolor")
        assert "custom deck mood" not in d.prompt

    def test_soft_storybook_watercolor_does_not_include_palette(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._deck()
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="soft_storybook_watercolor")
        assert "#AABBCC" not in d.prompt

    def test_soft_storybook_watercolor_does_not_include_typography(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._deck()
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="soft_storybook_watercolor")
        assert "round serif" not in d.prompt

    def test_soft_storybook_watercolor_does_not_include_decorations(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._deck()
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="soft_storybook_watercolor")
        assert "glowing stars" not in d.prompt

    def test_soft_storybook_watercolor_includes_audience(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._deck()
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="soft_storybook_watercolor")
        assert "children" in d.prompt

    # --- Fixed preset: cute_hand_drawn_cartoon ---

    def test_cute_hand_drawn_cartoon_appears_in_prompt(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._deck()
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="cute_hand_drawn_cartoon")
        assert "cute_hand_drawn_cartoon" in d.prompt
        assert "rounded simplified characters" in d.prompt

    def test_cute_hand_drawn_cartoon_does_not_include_deck_mood(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._deck()
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="cute_hand_drawn_cartoon")
        assert "custom deck mood" not in d.prompt

    # --- Fixed preset: paper_cut_collage_storybook ---

    def test_paper_cut_collage_storybook_appears_in_prompt(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._deck()
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="paper_cut_collage_storybook")
        assert "paper_cut_collage_storybook" in d.prompt
        assert "layered paper texture" in d.prompt

    def test_paper_cut_collage_does_not_include_deck_mood(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._deck()
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="paper_cut_collage_storybook")
        assert "custom deck mood" not in d.prompt

    # --- deck_style mode ---

    def test_deck_style_uses_deck_mood(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._deck()
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="deck_style")
        assert "custom deck mood" in d.prompt

    def test_deck_style_uses_palette(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._deck()
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="deck_style")
        assert "#AABBCC" in d.prompt

    def test_deck_style_uses_typography(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._deck()
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="deck_style")
        assert "round serif" in d.prompt

    def test_deck_style_uses_decorations(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._deck()
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="deck_style")
        assert "glowing stars" in d.prompt

    def test_deck_style_does_not_include_any_preset_description(self):
        from open_keynote_agent.images.director import build_directed_image_prompt, STYLE_MODES
        deck = self._deck()
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="deck_style")
        for preset_id, preset_desc in STYLE_MODES.items():
            if preset_id == "deck_style":
                continue
            assert preset_id not in d.prompt
            # Check a unique fragment from each preset description
            if preset_desc:
                first_phrase = preset_desc.split(",")[0]
                assert first_phrase not in d.prompt, f"Preset description leaked: {first_phrase!r}"

    # --- Style guardrails ---

    def test_style_guardrails_in_negative_prompt_default_mode(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._deck()
        d = build_directed_image_prompt(deck, deck.slides[0])
        neg = d.negative_prompt or ""
        for term in ("not photorealistic", "not cinematic", "not realistic portrait",
                     "not movie still", "not 3D render", "not adult editorial illustration"):
            assert term in neg, f"Missing guardrail: {term!r}"

    def test_style_guardrails_in_negative_prompt_deck_style_mode(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        deck = self._deck()
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="deck_style")
        neg = d.negative_prompt or ""
        for term in ("not photorealistic", "not cinematic"):
            assert term in neg

    def test_style_guardrails_in_negative_prompt_all_presets(self):
        from open_keynote_agent.images.director import build_directed_image_prompt, STYLE_MODES
        deck = self._deck()
        for mode_id in STYLE_MODES:
            d = build_directed_image_prompt(deck, deck.slides[0], style_mode=mode_id)
            neg = d.negative_prompt or ""
            assert "not photorealistic" in neg, f"Missing guardrail for mode {mode_id!r}"

    def test_guardrail_suppressed_when_deck_style_mood_is_cinematic(self):
        # In deck_style, if mood says "cinematic", the "not cinematic" guardrail must be omitted.
        from open_keynote_agent.images.director import build_directed_image_prompt
        raw = _minimal_deck_dict(n_slides=1)
        raw["style"]["mood"] = "cinematic 3D fairy-tale render"
        deck = DeckSpec(**raw)
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="deck_style")
        neg = d.negative_prompt or ""
        assert "not cinematic" not in neg
        assert "not 3D render" not in neg

    def test_guardrail_suppressed_when_deck_style_mood_is_photorealistic(self):
        from open_keynote_agent.images.director import build_directed_image_prompt
        raw = _minimal_deck_dict(n_slides=1)
        raw["style"]["mood"] = "photorealistic fairy-tale illustration"
        deck = DeckSpec(**raw)
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="deck_style")
        neg = d.negative_prompt or ""
        assert "not photorealistic" not in neg

    def test_guardrails_still_present_in_deck_style_with_neutral_mood(self):
        # When mood does not mention any guardrail keyword, all guardrails remain.
        from open_keynote_agent.images.director import build_directed_image_prompt
        raw = _minimal_deck_dict(n_slides=1)
        raw["style"]["mood"] = "warm cozy storybook"
        deck = DeckSpec(**raw)
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="deck_style")
        neg = d.negative_prompt or ""
        for term in ("not photorealistic", "not cinematic", "not 3D render"):
            assert term in neg, f"Expected guardrail {term!r} for neutral mood"

    def test_fixed_preset_always_keeps_all_guardrails(self):
        # Fixed presets never request photorealistic/cinematic styles, so guardrails are always kept.
        from open_keynote_agent.images.director import build_directed_image_prompt
        raw = _minimal_deck_dict(n_slides=1)
        raw["style"]["mood"] = "cinematic"  # mood is irrelevant for fixed presets
        deck = DeckSpec(**raw)
        d = build_directed_image_prompt(deck, deck.slides[0], style_mode="soft_storybook_watercolor")
        neg = d.negative_prompt or ""
        assert "not cinematic" in neg
        assert "not photorealistic" in neg

    # --- Default mode end-to-end via planner ---

    def test_default_mode_prompt_contains_watercolor_preset(self):
        deck = self._deck()
        spec = build_slide_art_specs(deck)[0]
        assert "soft_storybook_watercolor" in spec.image.prompt
        assert spec.image.style == "soft_storybook_watercolor"

    def test_explicit_style_mode_via_planner(self):
        deck = self._deck()
        spec = build_slide_art_specs(deck, style_mode="cute_hand_drawn_cartoon")[0]
        assert "cute_hand_drawn_cartoon" in spec.image.prompt
        assert "rounded simplified characters" in spec.image.prompt
        assert spec.image.style == "cute_hand_drawn_cartoon"

    # --- CLI --style ---

    def test_cli_style_option_accepted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        spec_path = _write_deck_spec(tmp_path)
        out = tmp_path / "out"
        result = cli_runner.invoke(app, [
            "generate-images", str(spec_path), "--output", str(out),
            "--provider", "fake", "--style", "cute_hand_drawn_cartoon",
        ])
        assert result.exit_code == 0, result.output
        data = json.loads((out / "art_spec.json").read_text())
        assert any("cute_hand_drawn_cartoon" in s["image"]["prompt"] for s in data["slides"])
        assert all(s["image"]["style"] == "cute_hand_drawn_cartoon" for s in data["slides"])

    def test_cli_unknown_style_exits_nonzero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        spec_path = _write_deck_spec(tmp_path)
        result = cli_runner.invoke(app, [
            "generate-images", str(spec_path), "--provider", "fake", "--style", "bad_mode",
        ])
        assert result.exit_code != 0
        assert "bad_mode" in result.output

    def test_cli_dry_run_with_style(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        spec_path = _write_deck_spec(tmp_path)
        out = tmp_path / "out"
        result = cli_runner.invoke(app, [
            "generate-images", str(spec_path), "--output", str(out),
            "--dry-run", "--style", "paper_cut_collage_storybook",
        ])
        assert result.exit_code == 0, result.output
        data = json.loads((out / "art_spec.json").read_text())
        assert any("paper_cut_collage_storybook" in s["image"]["prompt"] for s in data["slides"])
        assert all(s["image"]["style"] == "paper_cut_collage_storybook" for s in data["slides"])
        assert not (out / "image_manifest.json").exists()

    def test_cli_dry_run_with_style_and_slides(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        spec_path = _write_deck_spec(tmp_path, n_slides=4)
        out = tmp_path / "out"
        result = cli_runner.invoke(app, [
            "generate-images", str(spec_path), "--output", str(out),
            "--dry-run", "--style", "deck_style", "--slides", "1,3",
        ])
        assert result.exit_code == 0, result.output
        data = json.loads((out / "art_spec.json").read_text())
        assert [s["slide_index"] for s in data["slides"]] == [1, 3]
        assert all(s["image"]["style"] == "deck_style" for s in data["slides"])

    def test_cli_omitted_style_is_backwards_compatible(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        spec_path = _write_deck_spec(tmp_path)
        out = tmp_path / "out"
        result = cli_runner.invoke(app, [
            "generate-images", str(spec_path), "--output", str(out), "--provider", "fake",
        ])
        assert result.exit_code == 0, result.output
        # Default (soft_storybook_watercolor) should be used
        data = json.loads((out / "art_spec.json").read_text())
        assert any("soft_storybook_watercolor" in s["image"]["prompt"] for s in data["slides"])
        assert all(s["image"]["style"] == "soft_storybook_watercolor" for s in data["slides"])
