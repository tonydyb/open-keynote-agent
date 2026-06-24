from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class RunSession(BaseModel):
    run_id: str
    target_dir: Path
    command: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_path: Path | None = None
    plan_path: Path | None = None
    tool_calls_path: Path | None = None
    result_path: Path | None = None

    @property
    def root_dir(self) -> Path:
        return Path(".runs") / self.run_id

    def ensure_dir(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def write_json(self, name: str, payload: Any) -> Path:
        if not self.root_dir.exists():
            self.ensure_dir()
        path = self.root_dir / name
        path.write_text(json.dumps(payload, default=str, indent=2, ensure_ascii=False))
        return path

    def write_request(self, request_data: dict) -> Path:
        path = self.write_json("request.json", request_data)
        self.request_path = path
        return path

    def write_plan(self, plan_data: dict) -> Path:
        path = self.write_json("plan.json", plan_data)
        self.plan_path = path
        return path

    def append_tool_call(self, tool_call: dict) -> Path:
        if not self.root_dir.exists():
            self.ensure_dir()
        path = self.root_dir / "tool_calls.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(tool_call, default=str, ensure_ascii=False) + "\n")
        self.tool_calls_path = path
        return path

    def write_result(self, result_data: dict) -> Path:
        path = self.write_json("result.json", result_data)
        self.result_path = path
        return path


def create_run_session(target_dir: Path, command: str) -> RunSession:
    run_id = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    return RunSession(run_id=run_id, target_dir=target_dir.resolve(), command=command)
