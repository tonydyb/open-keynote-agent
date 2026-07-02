import builtins
import json
import sys
from types import ModuleType

import pytest

from open_keynote_agent.llm.bedrock import BedrockConverseClient
from open_keynote_agent.llm.gemini import GeminiClient
from open_keynote_agent.llm.openai import OpenAIClient


class DummyOpenAIResponse:
    def __init__(self, text: str):
        self.output = [
            {
                "content": [
                    {
                        "text": text,
                    }
                ]
            }
        ]


class DummyGeminiResponse:
    def __init__(self, text: str):
        self.text = text


def test_bedrock_complete_json_returns_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    model_id = "test-bedrock"
    client = BedrockConverseClient(model_id=model_id, region="us-west-2")
    expected_response = {"organize_request": {"target_dir": ".", "dry_run": True}}

    class FakeClient:
        def converse(self, modelId: str, system: list[dict[str, str]], messages: list[dict], inferenceConfig: dict):
            assert modelId == model_id
            assert "Return only valid JSON" in system[0]["text"]
            assert "JSON schema" in system[0]["text"]
            assert messages == [{"role": "user", "content": [{"text": "hello"}]}]
            assert inferenceConfig == {"temperature": 0}
            return {
                "output": {
                    "message": {
                        "content": [{"text": f"```json\n{json.dumps(expected_response)}\n```"}],
                    }
                }
            }

    class FakeSession:
        def __init__(self, profile_name=None):
            self.profile_name = profile_name

        def client(self, service_name: str, region_name: str | None = None):
            assert service_name == "bedrock-runtime"
            assert region_name == "us-west-2"
            return FakeClient()

    fake_boto3 = ModuleType("boto3")
    fake_boto3.Session = FakeSession
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)

    result = client.complete_json([{"role": "user", "content": "hello"}], {"type": "object"})
    assert result == expected_response


def test_bedrock_missing_boto3_import_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "boto3":
            raise ImportError("No module named boto3")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    client = BedrockConverseClient(model_id="test-bedrock")
    with pytest.raises(ImportError, match="boto3 is required for BedrockConverseClient"):
        client.complete_json([{"role": "user", "content": "hi"}], {"type": "object"})


def test_bedrock_requires_model_id() -> None:
    with pytest.raises(ValueError, match="BEDROCK_MODEL_ID is required for Bedrock provider"):
        BedrockConverseClient(model_id="")


def test_openai_complete_json_returns_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenAIClient(api_key="fake-key", model="test-openai")
    expected_response = {"organize_request": {"target_dir": ".", "dry_run": True}}

    class FakeOpenAI:
        def __init__(self, api_key: str):
            assert api_key == "fake-key"

        @property
        def responses(self):
            class Responses:
                @staticmethod
                def create(model: str, input: list[dict[str, str]], text: dict, **kwargs):
                    assert model == "test-openai"
                    assert input == [
                        {"role": "system", "content": "Return only valid JSON matching the requested schema. Do not include any extra text."},
                        {"role": "user", "content": "hi"},
                    ]
                    assert "text_format" not in kwargs
                    assert text["format"]["type"] == "json_schema"
                    assert text["format"]["name"] == "structured_response"
                    assert text["format"]["schema"] == {"type": "object"}
                    assert text["format"]["strict"] is False
                    return DummyOpenAIResponse(f"```json\n{json.dumps(expected_response)}\n```")

            return Responses()

    fake_openai = ModuleType("openai")
    fake_openai.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "openai" or name.startswith("openai."):
            return fake_openai
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    result = client.complete_json([{"role": "user", "content": "hi"}], {"type": "object"})
    assert result == expected_response


def test_openai_missing_openai_import_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "openai":
            raise ImportError("No module named openai")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    client = OpenAIClient(api_key="fake-key", model="test-openai")
    with pytest.raises(ImportError, match="openai is required for OpenAIClient"):
        client.complete_json([{"role": "user", "content": "hi"}], {"type": "object"})


def test_openai_requires_api_key() -> None:
    with pytest.raises(ValueError, match="OPENAI_API_KEY is required for OpenAI provider"):
        OpenAIClient(api_key="", model="test-openai")


def test_gemini_complete_json_returns_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    client = GeminiClient(api_key="fake-key", model="test-gemini")
    expected_response = {"organize_request": {"target_dir": ".", "dry_run": True}}

    class FakeGenAI(ModuleType):
        def __init__(self):
            super().__init__("google.genai")

        class Client:
            def __init__(self, api_key: str):
                assert api_key == "fake-key"

                class Models:
                    @staticmethod
                    def generate_content(model: str, contents: str, config):
                        assert model == "test-gemini"
                        assert contents.startswith("hi\n\nReturn JSON matching this JSON schema")
                        assert '"type": "object"' in contents
                        assert config.system_instruction == "Return only valid JSON matching the requested schema. Do not include any extra text."
                        assert config.temperature == 0.0
                        assert config.response_mime_type == "application/json"
                        assert config.response_json_schema is None
                        assert config.response_schema is None
                        return DummyGeminiResponse(f"```json\n{json.dumps(expected_response)}\n```")

                self.models = Models()

    class FakeGenerateContentConfig:
        def __init__(
            self,
            system_instruction: str,
            temperature: float,
            response_mime_type: str,
            response_json_schema: dict | None = None,
            response_schema: dict | None = None,
        ):
            self.system_instruction = system_instruction
            self.temperature = temperature
            self.response_mime_type = response_mime_type
            self.response_json_schema = response_json_schema
            self.response_schema = response_schema

    fake_google = ModuleType("google")
    fake_google.genai = FakeGenAI()
    fake_google_genai_types = ModuleType("google.genai.types")
    fake_google_genai_types.GenerateContentConfig = FakeGenerateContentConfig
    fake_google.genai.types = fake_google_genai_types
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_google.genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_google_genai_types)

    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "google":
            return fake_google
        if name == "google.genai":
            return fake_google.genai
        if name == "google.genai.types":
            return fake_google_genai_types
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    result = client.complete_json([{"role": "user", "content": "hi"}], {"type": "object"})
    assert result == expected_response


def test_gemini_missing_google_genai_import_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "google":
            raise ImportError("No module named google")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(ImportError, match="google-genai is required for GeminiClient"):
        GeminiClient(api_key="fake-key", model="test-gemini").complete_json(
            [{"role": "user", "content": "hi"}],
            {"type": "object"},
        )


def test_gemini_requires_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    with pytest.raises(ValueError, match="GEMINI_MODEL is required for Gemini provider"):
        GeminiClient(api_key="fake-key", model=None)


def test_gemini_missing_api_key_or_model_rejects() -> None:
    with pytest.raises(ValueError, match="GEMINI_API_KEY is required for Gemini provider"):
        GeminiClient(api_key="", model="test-gemini")
