from pathlib import Path

import pytest

from open_mac_agent.organizer import (
    DEFAULT_CATEGORY,
    OrganizePlan,
    build_organize_plan,
    classify_file,
    scan_folder,
)


def test_classify_file_known_extension(tmp_path: Path) -> None:
    file_path = tmp_path / "report.pdf"
    file_path.write_text("pdf content")

    assert classify_file(file_path) == "PDFs"


def test_classify_file_unknown_extension(tmp_path: Path) -> None:
    file_path = tmp_path / "archive.bin"
    file_path.write_text("binary")

    assert classify_file(file_path) == DEFAULT_CATEGORY


def test_scan_folder_only_returns_regular_files(tmp_path: Path) -> None:
    (tmp_path / "file.txt").write_text("hello")
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "nested.txt").write_text("nested")

    files = scan_folder(tmp_path)
    assert len(files) == 1
    assert files[0].name == "file.txt"


def test_scan_folder_nonexistent_raises(tmp_path: Path) -> None:
    missing_dir = tmp_path / "missing"
    with pytest.raises(ValueError, match="Target directory does not exist"):
        scan_folder(missing_dir)


def test_build_organize_plan_creates_operations(tmp_path: Path) -> None:
    pdf_file = tmp_path / "report.pdf"
    image_file = tmp_path / "photo.png"
    doc_file = tmp_path / "notes.md"

    pdf_file.write_text("pdf")
    image_file.write_text("image")
    doc_file.write_text("doc")

    plan = build_organize_plan(tmp_path)

    assert isinstance(plan, OrganizePlan)
    assert len(plan.operations) == 3
    assert not plan.skipped

    destinations = {op.destination.name for op in plan.operations}
    assert destinations == {"report.pdf", "photo.png", "notes.md"}

    categories = {op.category for op in plan.operations}
    assert categories == {"PDFs", "Images", "Documents"}


def test_build_organize_plan_skips_existing_destination(tmp_path: Path) -> None:
    source = tmp_path / "report.pdf"
    source.write_text("pdf")

    target_dir = tmp_path / "PDFs"
    target_dir.mkdir()
    destination = target_dir / "report.pdf"
    destination.write_text("already exists")

    plan = build_organize_plan(tmp_path)

    assert len(plan.operations) == 0
    assert len(plan.skipped) == 1
    skipped = plan.skipped[0]
    assert skipped.source == source
    assert "Destination already exists" in skipped.reason


def test_build_organize_plan_filters_categories(tmp_path: Path) -> None:
    pdf_file = tmp_path / "report.pdf"
    csv_file = tmp_path / "data.csv"
    pdf_file.write_text("pdf")
    csv_file.write_text("csv")

    plan = build_organize_plan(tmp_path, categories=["PDFs"])

    assert len(plan.operations) == 1
    assert plan.operations[0].category == "PDFs"
    assert len(plan.skipped) == 1
    assert plan.skipped[0].source == csv_file
    assert "Category not selected" in plan.skipped[0].reason
