from __future__ import annotations

import json
from typing import Any

from open_mac_agent.llm.base import LLMClient
from open_mac_agent.llm.json_utils import parse_json_object

SYSTEM_PROMPT = "Return only valid JSON matching the requested schema. Do not include any extra text."


class BedrockConverseClient(LLMClient):
    def __init__(
        self,
        model_id: str,
        region: str | None = None,
        profile: str | None = None,
    ) -> None:
        if not model_id:
            raise ValueError("BEDROCK_MODEL_ID is required for Bedrock provider")
        self.model_id = model_id
        self.region = region
        self.profile = profile

    def complete_json(self, messages: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
        try:
            import boto3
        except ImportError as exc:
            raise ImportError("boto3 is required for BedrockConverseClient") from exc

        session = boto3.Session(profile_name=self.profile) if self.profile else boto3.Session()
        client = session.client("bedrock-runtime", region_name=self.region)
        prompt = "\n".join(message["content"] for message in messages)
        schema_text = json.dumps(schema)
        response = client.converse(
            modelId=self.model_id,
            system=[{"text": f"{SYSTEM_PROMPT}\nJSON schema: {schema_text}"}],
            messages=[
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ],
            inferenceConfig={"temperature": 0},
        )

        output = response.get("output", {}) if isinstance(response, dict) else getattr(response, "output", {})
        message = output.get("message", {}) if isinstance(output, dict) else getattr(output, "message", {})
        content = message.get("content", []) if isinstance(message, dict) else getattr(message, "content", [])
        for block in content:
            text = block.get("text") if isinstance(block, dict) else getattr(block, "text", None)
            if text:
                return parse_json_object(text)

        raise ValueError("Bedrock response did not contain a JSON text payload")
