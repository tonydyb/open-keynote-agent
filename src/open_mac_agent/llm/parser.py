from __future__ import annotations

import os

from open_mac_agent.llm.base import LLMClient
from open_mac_agent.llm.fake import FakeLLMClient
from open_mac_agent.llm.schema import LLMPlanResponse, validate_llm_plan


class UnsupportedProviderError(ValueError):
    pass


def load_llm_client_from_env() -> LLMClient:
    provider = os.environ.get("OMA_LLM_PROVIDER", "fake").lower()
    if provider == "fake":
        return FakeLLMClient()

    raise UnsupportedProviderError(
        f"Unsupported LLM provider: {provider}. Valid providers are fake."
    )


def parse_natural_language_request(client: LLMClient, prompt: str) -> LLMPlanResponse:
    schema = {
        "type": "object",
        "properties": {
            "organize_request": {
                "type": "object",
                "properties": {
                    "target_dir": {"type": "string"},
                    "categories": {
                        "type": ["array", "null"],
                        "items": {"type": "string"},
                    },
                    "dry_run": {"type": "boolean"},
                },
                "required": ["target_dir"],
            }
        },
        "required": ["organize_request"],
    }
    response = client.complete_json([{"role": "user", "content": prompt}], schema)
    try:
        return validate_llm_plan(response)
    except Exception as exc:
        raise ValueError(f"LLM response validation failed: {exc}") from exc
