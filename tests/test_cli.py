import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import open_keynote_agent.cli as cli_module
from open_keynote_agent.cli import app
from open_keynote_agent.llm.fake import FakeLLMClient


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


def test_ask_defaults_to_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "report.pdf"
    source.write_text("pdf")
    client = FakeLLMClient(
        response={
            "organize_request": {
                "target_dir": str(tmp_path),
                "categories": ["PDFs"],
                "dry_run": True,
            }
        }
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: client)
    result = runner.invoke(app, ["ask", "organize my pdf files"])

    assert result.exit_code == 0
    assert "Dry-run mode: no files were moved." in result.output
    assert source.exists()
    assert not (tmp_path / "PDFs" / "report.pdf").exists()
    assert client.calls

    run_dir = next((tmp_path / ".runs").iterdir())
    request_data = json.loads((run_dir / "request.json").read_text())
    assert request_data["command"] == "ask"
    assert request_data["mode"] == "dry-run"
    plan_data = json.loads((run_dir / "plan.json").read_text())
    assert len(plan_data["operations"]) == 1


def test_ask_apply_moves_files_when_confirmed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "report.pdf"
    source.write_text("pdf")
    client = FakeLLMClient(
        response={
            "organize_request": {
                "target_dir": str(tmp_path),
                "categories": ["PDFs"],
                "dry_run": False,
            }
        }
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: client)
    result = runner.invoke(app, ["ask", "organize and apply my pdf files", "--apply"], input="y\n")

    assert result.exit_code == 0
    assert "Apply confirmed." in result.output
    assert not source.exists()
    assert (tmp_path / "PDFs" / "report.pdf").exists()

    run_dir = next((tmp_path / ".runs").iterdir())
    result_data = json.loads((run_dir / "result.json").read_text())
    assert result_data["status"] == "confirmed"
    assert result_data["moved"] == ["PDFs/report.pdf"]


def test_ask_rejects_missing_target_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeLLMClient(
        response={
            "organize_request": {
                "target_dir": str(tmp_path / "missing"),
                "categories": ["PDFs"],
                "dry_run": True,
            }
        }
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli_module, "load_llm_client_from_env", lambda: client)
    result = runner.invoke(app, ["ask", "organize missing folder"])

    assert result.exit_code != 0
    assert "Target directory does not exist" in result.output
    assert not (tmp_path / ".runs").exists()
