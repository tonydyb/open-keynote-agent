import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from open_mac_agent.cli import app


runner = CliRunner()


def test_organize_dry_run_does_not_move_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "report.pdf"
    source.write_text("pdf")

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["organize", str(tmp_path), "--dry-run"])

    assert result.exit_code == 0
    assert "Dry-run mode: no files were moved." in result.output
    assert source.exists()
    assert not (tmp_path / "PDFs" / "report.pdf").exists()

    runs_dir = tmp_path / ".runs"
    assert runs_dir.exists() and runs_dir.is_dir()
    run_dirs = list(runs_dir.iterdir())
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    assert (run_dir / "request.json").exists()
    assert (run_dir / "plan.json").exists()
    assert (run_dir / "tool_calls.jsonl").exists()
    assert (run_dir / "result.json").exists()

    request_data = json.loads((run_dir / "request.json").read_text())
    assert request_data["mode"] == "dry-run"


def test_organize_apply_requires_confirmation_and_does_not_move_when_declined(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "report.pdf"
    source.write_text("pdf")

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["organize", str(tmp_path), "--apply"], input="n\n")

    assert result.exit_code == 0
    assert "Apply these moves?" in result.output
    assert "Apply cancelled. No files were moved." in result.output
    assert source.exists()
    assert not (tmp_path / "PDFs" / "report.pdf").exists()

    runs_dir = tmp_path / ".runs"
    assert runs_dir.exists() and runs_dir.is_dir()
    run_dirs = list(runs_dir.iterdir())
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    assert (run_dir / "result.json").exists()
    result_data = json.loads((run_dir / "result.json").read_text())
    assert result_data["status"] == "cancelled"


def test_organize_apply_moves_files_when_confirmed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "report.pdf"
    source.write_text("pdf")

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["organize", str(tmp_path), "--apply"], input="y\n")

    assert result.exit_code == 0
    assert "Apply confirmed." in result.output
    assert not source.exists()
    assert (tmp_path / "PDFs" / "report.pdf").exists()

    runs_dir = tmp_path / ".runs"
    assert runs_dir.exists() and runs_dir.is_dir()
    run_dirs = list(runs_dir.iterdir())
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    result_data = json.loads((run_dir / "result.json").read_text())
    assert result_data["status"] == "confirmed"
    assert result_data["moved"] == ["PDFs/report.pdf"]
