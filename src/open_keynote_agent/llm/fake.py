from __future__ import annotations

from typing import Any

from open_keynote_agent.llm.base import LLMClient


class FakeLLMClient(LLMClient):
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def complete_json(self, messages: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"messages": messages, "schema": schema})
        if self.response is None:
            raise ValueError(
                "FakeLLMClient has no configured response. Set OMA_LLM_PROVIDER to "
                "bedrock, openai, or gemini for natural-language parsing, or inject "
                "FakeLLMClient(response=...) in tests."
            )
        return self.response
