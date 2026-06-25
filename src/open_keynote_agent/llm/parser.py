from __future__ import annotations

import os

from dotenv import load_dotenv

from open_keynote_agent.llm.base import LLMClient
from open_keynote_agent.llm.bedrock import BedrockConverseClient
from open_keynote_agent.llm.fake import FakeLLMClient
from open_keynote_agent.llm.gemini import GeminiClient
from open_keynote_agent.llm.openai import OpenAIClient
from open_keynote_agent.llm.schema import LLMPlanResponse, validate_llm_plan


class UnsupportedProviderError(ValueError):
    pass


def load_llm_client_from_env() -> LLMClient:
    if os.environ.get("OMA_SKIP_DOTENV") != "1":
        load_dotenv()
    provider = os.environ.get("OMA_LLM_PROVIDER", "fake").lower()
    if provider == "fake":
        return FakeLLMClient()
    if provider == "bedrock":
        return BedrockConverseClient(
            model_id=os.environ.get("BEDROCK_MODEL_ID", ""),
            region=os.environ.get("AWS_REGION"),
            profile=os.environ.get("AWS_PROFILE"),
        )
    if provider == "openai":
        return OpenAIClient(
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            model=os.environ.get("OPENAI_MODEL"),
        )
    if provider == "gemini":
        return GeminiClient(
            api_key=os.environ.get("GEMINI_API_KEY", ""),
            model=os.environ.get("GEMINI_MODEL"),
        )

    raise UnsupportedProviderError(
        f"Unsupported LLM provider: {provider}. Valid providers are fake, bedrock, openai, gemini."
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
