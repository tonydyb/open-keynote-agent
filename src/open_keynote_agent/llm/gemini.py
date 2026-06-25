from __future__ import annotations

import os
from typing import Any

from open_keynote_agent.llm.base import LLMClient
from open_keynote_agent.llm.json_utils import parse_json_object

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
            from google.genai import types
        except ImportError as exc:
            raise ImportError("google-genai is required for GeminiClient") from exc

        prompt = "\n".join(message["content"] for message in messages)
        client = genai.Client(api_key=self.api_key)
        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )

        text = getattr(response, "text", None)
        if text is None:
            raise ValueError("Gemini response did not contain a JSON string payload")

        return parse_json_object(text)
