from __future__ import annotations

import json
import os
from typing import Any

from open_mac_agent.llm.base import LLMClient

SYSTEM_PROMPT = "Return only valid JSON matching the requested schema. Do not include any extra text."


class GeminiClient(LLMClient):
    def __init__(self, api_key: str, model: str | None = None) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required for Gemini provider")
        self.api_key = api_key
        self.model = model or os.environ.get("GEMINI_MODEL")
        if not self.model:
            raise ValueError("GEMINI_MODEL is required for Gemini provider")

    def complete_json(self, messages: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
        try:
            from google import genai
        except ImportError as exc:
            raise ImportError("google-genai is required for GeminiClient") from exc

        prompt = "\n".join(message["content"] for message in messages)
        model = genai.TextGenerationModel.from_pretrained(self.model)
        response = model.generate(prompt=f"{SYSTEM_PROMPT}\n{prompt}", temperature=0.0)

        text = getattr(response, "text", None)
        if text is None:
            generations = getattr(response, "generations", None)
            if isinstance(generations, list) and generations:
                candidate = generations[0]
                text = getattr(candidate, "text", None)
                if text is None and isinstance(candidate, dict):
                    text = candidate.get("text")

        if text is None:
            raise ValueError("Gemini response did not contain a JSON string payload")

        return json.loads(text)
