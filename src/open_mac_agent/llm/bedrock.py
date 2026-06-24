from __future__ import annotations

import json
from typing import Any

from open_mac_agent.llm.base import LLMClient

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
        response = client.converse(
            modelId=self.model_id,
            input=f"{SYSTEM_PROMPT}\n{prompt}",
            contentType="application/json",
        )

        body = None
        if isinstance(response, dict):
            body = response.get("body")
        else:
            body = getattr(response, "body", None)

        if hasattr(body, "read"):
            body = body.read().decode("utf-8")
        if isinstance(body, bytes):
            body = body.decode("utf-8")
        if not isinstance(body, str):
            raise ValueError("Bedrock response did not contain a JSON string body")

        return json.loads(body)
