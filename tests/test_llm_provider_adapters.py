import builtins
import json
import sys
from types import ModuleType

import pytest

from open_mac_agent.llm.bedrock import BedrockConverseClient
from open_mac_agent.llm.gemini import GeminiClient
from open_mac_agent.llm.openai import OpenAIClient


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


class DummyGeminiGeneration:
    def __init__(self, text: str):
        self.text = text


class DummyGeminiResponse:
    def __init__(self, text: str):
        self.generations = [DummyGeminiGeneration(text)]


def test_bedrock_complete_json_returns_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    model_id = "test-bedrock"
    client = BedrockConverseClient(model_id=model_id, region="us-west-2")
    expected_response = {"organize_request": {"target_dir": ".", "dry_run": True}}

    class FakeClient:
        def converse(self, modelId: str, input: str, contentType: str):
            assert modelId == model_id
            assert contentType == "application/json"
            return {"body": json.dumps(expected_response)}

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
                def create(model: str, input: list[dict[str, str]], text_format: dict[str, dict[str, str]]):
                    assert model == "test-openai"
                    return DummyOpenAIResponse(json.dumps(expected_response))

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

    class FakeModel:
        @staticmethod
        def generate(prompt: str, temperature: float):
            assert "Return only valid JSON" in prompt
            return DummyGeminiResponse(json.dumps(expected_response))

    class FakeGenAI(ModuleType):
        def __init__(self):
            super().__init__("google.genai")

        class TextGenerationModel:
            @staticmethod
            def from_pretrained(model: str):
                assert model == "test-gemini"
                return FakeModel()

    fake_google = ModuleType("google")
    fake_google.genai = FakeGenAI
    monkeypatch.setitem(sys.modules, "google", fake_google)

    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "google" or name.startswith("google."):
            return fake_google
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
    with pytest.raises(ValueError, match="GEMINI_MODEL is required for Gemini provider"):
        GeminiClient(api_key="fake-key", model=None)


def test_gemini_missing_api_key_or_model_rejects() -> None:
    with pytest.raises(ValueError, match="GEMINI_API_KEY is required for Gemini provider"):
        GeminiClient(api_key="", model="test-gemini")
