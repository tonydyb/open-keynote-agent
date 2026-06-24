from __future__ import annotations

from typing import Any, Protocol


class LLMClient(Protocol):
    def complete_json(self, messages: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
        """Complete a JSON response for the provided messages and schema."""
        ...
