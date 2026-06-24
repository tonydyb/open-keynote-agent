from __future__ import annotations

import os
from typing import Any

from open_mac_agent.llm.base import LLMClient
from open_mac_agent.llm.json_utils import parse_json_object

SYSTEM_PROMPT = "Return only valid JSON matching the requested schema. Do not include any extra text."


class OpenAIClient(LLMClient):
    def __init__(self, api_key: str, model: str | None = None) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider")
        self.api_key = api_key
        self.model = model or os.environ.get("OPENAI_MODEL")

    def complete_json(self, messages: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError("openai is required for OpenAIClient") from exc

        client = OpenAI(api_key=self.api_key)
        prompt = "\n".join(message["content"] for message in messages)
        response = client.responses.create(
            model=self.model,
            input=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            text_format={"type": "json_schema", "json_schema": schema},
        )

        text = getattr(response, "output_text", None)
        if text is None:
            output = getattr(response, "output", None)
            if isinstance(output, list) and output:
                first = output[0]
                contents = getattr(first, "content", None)
                if isinstance(contents, list) and contents:
                    candidate = contents[0]
                    text = getattr(candidate, "text", None)
                    if text is None and isinstance(candidate, dict):
                        text = candidate.get("text")
                elif isinstance(first, dict):
                    contents = first.get("content")
                    if isinstance(contents, list) and contents:
                        candidate = contents[0]
                        if isinstance(candidate, dict):
                            text = candidate.get("text")
            elif isinstance(output, dict):
                nested = output.get("output", [])
                if isinstance(nested, list) and nested:
                    candidate = nested[0]
                    if isinstance(candidate, dict):
                        content = candidate.get("content", [])
                        if isinstance(content, list) and content:
                            text = content[0].get("text")

        if text is None:
            raise ValueError("OpenAI response did not contain a JSON string payload")

        return parse_json_object(text)
