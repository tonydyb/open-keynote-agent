from __future__ import annotations

from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, Field, field_validator

CATEGORY_EXTENSIONS = {
    "PDFs": {".pdf"},
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".tiff", ".bmp", ".svg"},
    "Documents": {".doc", ".docx", ".txt", ".md", ".rtf", ".pages"},
    "Spreadsheets": {".xls", ".xlsx", ".csv", ".tsv", ".numbers"},
    "Presentations": {".ppt", ".pptx", ".key"},
    "Archives": {".zip", ".tar", ".gz", ".tgz", ".rar", ".7z"},
    "Audio": {".mp3", ".wav", ".m4a", ".flac", ".aac"},
    "Video": {".mp4", ".mov", ".mkv", ".avi", ".webm"},
    "Code": {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".rb", ".php", ".html", ".css", ".json", ".yaml", ".yml", ".toml"},
}

DEFAULT_CATEGORY = "Others"


def classify_file(path: Path) -> str:
    """Classify a file by extension into a category name."""
    suffix = path.suffix.lower()
    for category, extensions in CATEGORY_EXTENSIONS.items():
        if suffix in extensions:
            return category
    return DEFAULT_CATEGORY


def scan_folder(target_dir: Path) -> list[Path]:
    """Return regular files in the target directory only (non-recursive)."""
    target_dir = target_dir.resolve()
    if not target_dir.exists() or not target_dir.is_dir():
        raise ValueError(f"Target directory does not exist: {target_dir}")

    return [child for child in target_dir.iterdir() if child.is_file()]


class MoveOperation(BaseModel):
    source: Path
    destination: Path
    category: str


class SkippedFile(BaseModel):
    source: Path
    reason: str


class OrganizePlan(BaseModel):
    target_dir: Path
    operations: list[MoveOperation] = Field(default_factory=list)
    skipped: list[SkippedFile] = Field(default_factory=list)

    @field_validator("target_dir", mode="before")
    def normalize_target_dir(cls, value: Path) -> Path:
        return Path(value).resolve()


def build_organize_plan(target_dir: Path, categories: Iterable[str] | None = None) -> OrganizePlan:
    target_dir = Path(target_dir)
    plan = OrganizePlan(target_dir=target_dir)
    allowed_categories = set(categories) if categories is not None else None

    for source in scan_folder(target_dir):
        category = classify_file(source)
        if allowed_categories is not None and category not in allowed_categories:
            plan.skipped.append(SkippedFile(source=source, reason="Category not selected"))
            continue

        destination = target_dir / category / source.name
        destination = destination.resolve()

        try:
            destination.relative_to(target_dir.resolve())
        except ValueError:
            plan.skipped.append(SkippedFile(source=source, reason="Unsafe destination path"))
            continue

        if destination.exists():
            plan.skipped.append(SkippedFile(source=source, reason="Destination already exists"))
            continue

        plan.operations.append(MoveOperation(source=source, destination=destination, category=category))

    return plan
