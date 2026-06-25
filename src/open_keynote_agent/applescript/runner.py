from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Protocol


@dataclass
class ScriptRunResult:
    stdout: str
    stderr: str
    returncode: int

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class ScriptRunner(Protocol):
    def run(self, script: str) -> ScriptRunResult: ...


class OsascriptRunner:
    def run(self, script: str) -> ScriptRunResult:
        try:
            proc = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("osascript timed out")
        return ScriptRunResult(
            stdout=proc.stdout,
            stderr=proc.stderr,
            returncode=proc.returncode,
        )


class FakeScriptRunner:
    def __init__(self, responses: dict[str, ScriptRunResult] | None = None) -> None:
        self.responses: dict[str, ScriptRunResult] = responses if responses is not None else {}
        self.calls: list[str] = []

    def run(self, script: str) -> ScriptRunResult:
        self.calls.append(script)
        if script in self.responses:
            return self.responses[script]
        return ScriptRunResult(stdout="", stderr="", returncode=0)
