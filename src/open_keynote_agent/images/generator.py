from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from open_keynote_agent.deck.schema import DeckSpec
from open_keynote_agent.images.planner import build_slide_art_specs
from open_keynote_agent.images.provider import ImageProvider
from open_keynote_agent.images.schema import ImageAsset, ImageManifest, SlideArtSpec


def _prompt_hash(art_spec: SlideArtSpec, provider_name: str) -> str:
    canonical = json.dumps(
        art_spec.image.model_dump(mode="json"),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(f"{provider_name}\n{canonical}".encode("utf-8")).hexdigest()[:16]


def _load_existing_manifest(manifest_path: Path) -> ImageManifest | None:
    if not manifest_path.exists():
        return None
    try:
        return ImageManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_atomically(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def generate_image_assets(
    deck: DeckSpec,
    provider: ImageProvider,
    *,
    output_dir: Path,
    force: bool = False,
    cache_dir: Path | None = None,
) -> ImageManifest:
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    # Shared cache is optional. CLI passes Path(".runs/image-cache/<provider>");
    # library callers and tests pass cache_dir=None to disable shared cache.
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = output_dir / "image_manifest.json"
    existing = _load_existing_manifest(manifest_path) if not force else None
    existing_by_index: dict[int, ImageAsset] = {}
    if existing is not None:
        for asset in existing.assets:
            existing_by_index[asset.slide_index] = asset

    art_specs = build_slide_art_specs(deck)
    assets: list[ImageAsset] = []

    for art_spec in art_specs:
        asset_path = assets_dir / art_spec.asset_filename
        phash = _prompt_hash(art_spec, provider.name)
        relative_asset = asset_path.relative_to(output_dir)

        cached = False
        if not force:
            # 1. Check shared cache (only when cache_dir provided)
            if cache_dir is not None:
                cache_file = cache_dir / f"{phash}.png"
                if cache_file.exists():
                    shutil.copy2(cache_file, asset_path)
                    cached = True

            # 2. Check same-output-dir manifest entry
            if not cached and art_spec.slide_index in existing_by_index:
                cached_entry = existing_by_index[art_spec.slide_index]
                cached_abs = output_dir / cached_entry.path
                if (
                    cached_entry.provider == provider.name
                    and cached_entry.prompt_hash == phash
                    and cached_abs.exists()
                ):
                    cached = True

        if not cached:
            provider.generate(art_spec.image, asset_path)
            # Populate shared cache when enabled
            if cache_dir is not None:
                shutil.copy2(asset_path, cache_dir / f"{phash}.png")

        assets.append(ImageAsset(
            slide_index=art_spec.slide_index,
            prompt_hash=phash,
            provider=provider.name,
            path=str(relative_asset),
            cached=cached,
        ))

    manifest = ImageManifest(
        deck_title=deck.title,
        provider=provider.name,
        assets_dir=str(Path("assets")),
        assets=assets,
    )

    # art_spec.json: {"deck_title": ..., "slides": [...]}
    art_spec_data = {
        "deck_title": deck.title,
        "slides": [s.model_dump() for s in art_specs],
    }
    _write_atomically(
        output_dir / "art_spec.json",
        json.dumps(art_spec_data, ensure_ascii=False, indent=2),
    )

    _write_atomically(
        manifest_path,
        json.dumps(manifest.model_dump(), ensure_ascii=False, indent=2),
    )

    return manifest
