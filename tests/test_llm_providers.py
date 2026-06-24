import pytest

from open_mac_agent.llm.fake import FakeLLMClient
from open_mac_agent.llm.parser import UnsupportedProviderError, load_llm_client_from_env


@pytest.fixture(autouse=True)
def skip_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OMA_SKIP_DOTENV", "1")


def test_load_fake_provider_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OMA_LLM_PROVIDER", raising=False)
    client = load_llm_client_from_env()
    assert isinstance(client, FakeLLMClient)


def test_load_bedrock_provider_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OMA_LLM_PROVIDER", "bedrock")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    client = load_llm_client_from_env()
    assert client.__class__.__name__ == "BedrockConverseClient"


def test_load_openai_provider_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OMA_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    client = load_llm_client_from_env()
    assert client.__class__.__name__ == "OpenAIClient"


def test_load_gemini_provider_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OMA_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setenv("GEMINI_MODEL", "test-gemini")
    client = load_llm_client_from_env()
    assert client.__class__.__name__ == "GeminiClient"


def test_load_unsupported_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OMA_LLM_PROVIDER", "unknown")
    with pytest.raises(UnsupportedProviderError):
        load_llm_client_from_env()
