from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class ProposedToolCall(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    description: str


class Plan(BaseModel):
    steps: list[ProposedToolCall]


class ToolResult(BaseModel):
    tool: str
    args: dict[str, Any]
    ok: bool
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    observation: str


class Turn(BaseModel):
    instruction: str
    plan: Plan
    approved: bool
    results: list[ToolResult] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list)


class SessionState(BaseModel):
    session_id: str = Field(
        default_factory=lambda: datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    )
    turns: list[Turn] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)

    def recent_observations(self, window: int = 10) -> list[str]:
        obs: list[str] = []
        for turn in self.turns[-window:]:
            obs.extend(turn.observations)
        return obs
