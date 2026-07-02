from __future__ import annotations

from pathlib import Path

from open_keynote_agent.images.schema import ImageManifest


def load_image_assets(manifest_path: Path) -> dict[int, Path]:
    """Load image_manifest.json and return a mapping from slide_index to absolute image path.

    Raises ValueError for:
    - Manifest file does not exist or is not a file
    - Invalid manifest JSON / schema
    - Absolute asset paths in the manifest
    - Duplicate slide_index entries
    - Listed asset files that do not exist or are not files
    """
    if not manifest_path.exists() or not manifest_path.is_file():
        raise ValueError(f"Image manifest not found: {manifest_path}")

    try:
        manifest = ImageManifest.model_validate_json(
            manifest_path.read_text(encoding="utf-8")
        )
    except Exception as exc:
        raise ValueError(f"Invalid image manifest {manifest_path}: {exc}") from exc

    manifest_dir = manifest_path.parent
    seen: set[int] = set()
    assets: dict[int, Path] = {}

    for asset in manifest.assets:
        asset_path = Path(asset.path)
        if asset_path.is_absolute():
            raise ValueError(
                f"Manifest asset path must be relative, got absolute path: {asset.path!r}"
            )
        if asset.slide_index in seen:
            raise ValueError(
                f"Duplicate slide_index {asset.slide_index} in manifest {manifest_path}"
            )
        seen.add(asset.slide_index)

        resolved = (manifest_dir / asset_path).resolve()
        if not resolved.exists() or not resolved.is_file():
            raise ValueError(
                f"Manifest asset for slide {asset.slide_index} not found: {resolved}"
            )

        assets[asset.slide_index] = resolved

    return assets
