from pathlib import Path

from open_mac_agent.filesystem import move_files
from open_mac_agent.organizer import OrganizePlan, MoveOperation


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
    assert "Source file missing" in result.skipped[0].reason
