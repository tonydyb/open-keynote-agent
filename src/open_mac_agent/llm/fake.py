from __future__ import annotations

from typing import Any

from open_mac_agent.llm.base import LLMClient


class FakeLLMClient(LLMClient):
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.response = response or {}
        self.calls: list[dict[str, Any]] = []

    def complete_json(self, messages: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"messages": messages, "schema": schema})
        return self.response
