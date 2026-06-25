from pathlib import Path

import pytest

from open_keynote_agent.filesystem import move_files
from open_keynote_agent.organizer import OrganizePlan, MoveOperation


def test_move_files_moves_files(tmp_path: Path) -> None:
    source = tmp_path / "report.pdf"
    source.write_text("pdf")
    destination = tmp_path / "PDFs" / "report.pdf"

    plan = OrganizePlan(
        target_dir=tmp_path,
        operations=[MoveOperation(source=source, destination=destination, category="PDFs")],
    )

    result = move_files(plan)

    assert result.moved == [destination]
    assert not result.skipped
    assert destination.exists()
    assert not source.exists()


def test_move_files_skips_existing_destination(tmp_path: Path) -> None:
    source = tmp_path / "report.pdf"
    source.write_text("pdf")
    destination = tmp_path / "PDFs" / "report.pdf"
    destination.parent.mkdir(parents=True)
    destination.write_text("existing")

    plan = OrganizePlan(
        target_dir=tmp_path,
        operations=[MoveOperation(source=source, destination=destination, category="PDFs")],
    )

    result = move_files(plan)

    assert not result.moved
    assert len(result.skipped) == 1
    assert result.skipped[0].source == source
    assert "Destination already exists" in result.skipped[0].reason
    assert source.exists()
    assert destination.exists()


def test_move_files_skips_missing_source(tmp_path: Path) -> None:
    source = tmp_path / "missing.pdf"
    destination = tmp_path / "PDFs" / "missing.pdf"

    plan = OrganizePlan(
        target_dir=tmp_path,
        operations=[MoveOperation(source=source, destination=destination, category="PDFs")],
    )

    result = move_files(plan)

    assert not result.moved
    assert len(result.skipped) == 1
    assert result.skipped[0].source == source
    assert "Source is not a regular file" in result.skipped[0].reason


def test_move_files_skips_source_outside_target_dir(tmp_path: Path) -> None:
    outside_dir = tmp_path / "outside"
    target_dir = tmp_path / "target"
    outside_dir.mkdir()
    target_dir.mkdir()
    source = outside_dir / "report.pdf"
    source.write_text("pdf")
    destination = target_dir / "PDFs" / "report.pdf"

    plan = OrganizePlan(
        target_dir=target_dir,
        operations=[MoveOperation(source=source, destination=destination, category="PDFs")],
    )

    result = move_files(plan)

    assert not result.moved
    assert len(result.skipped) == 1
    assert result.skipped[0].source == source
    assert "Source path outside target directory" in result.skipped[0].reason
    assert source.exists()
    assert not destination.exists()


def test_move_files_skips_directory_source(tmp_path: Path) -> None:
    source = tmp_path / "folder.pdf"
    source.mkdir()
    destination = tmp_path / "PDFs" / "folder.pdf"

    plan = OrganizePlan(
        target_dir=tmp_path,
        operations=[MoveOperation(source=source, destination=destination, category="PDFs")],
    )

    result = move_files(plan)

    assert not result.moved
    assert len(result.skipped) == 1
    assert result.skipped[0].source == source
    assert "Source is not a regular file" in result.skipped[0].reason
    assert source.exists()
    assert not destination.exists()


def test_move_files_skips_move_os_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / ".DS_Store"
    source.write_text("metadata")
    destination = tmp_path / "Others" / ".DS_Store"

    def raise_permission_error(self: Path, target: Path) -> Path:
        raise PermissionError(13, "Permission denied", str(self), str(target))

    monkeypatch.setattr(Path, "rename", raise_permission_error)

    plan = OrganizePlan(
        target_dir=tmp_path,
        operations=[MoveOperation(source=source, destination=destination, category="Others")],
    )

    result = move_files(plan)

    assert not result.moved
    assert len(result.skipped) == 1
    assert result.skipped[0].source == source
    assert "Move failed" in result.skipped[0].reason
    assert source.exists()
    assert not destination.exists()
