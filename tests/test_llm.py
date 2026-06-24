import pytest

from open_mac_agent.llm.fake import FakeLLMClient
from open_mac_agent.llm.parser import UnsupportedProviderError, load_llm_client_from_env, parse_natural_language_request
from open_mac_agent.llm.schema import OrganizeRequest


def test_load_fake_llm_client_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OMA_LLM_PROVIDER", raising=False)
    client = load_llm_client_from_env()
    assert isinstance(client, FakeLLMClient)


def test_load_fake_llm_client_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OMA_LLM_PROVIDER", "fake")
    client = load_llm_client_from_env()
    assert isinstance(client, FakeLLMClient)


def test_load_llm_client_unsupported_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OMA_LLM_PROVIDER", "openai")
    with pytest.raises(UnsupportedProviderError):
        load_llm_client_from_env()


def test_parse_natural_language_request_valid_response() -> None:
    response = {
        "organize_request": {
            "target_dir": ".",
            "categories": ["PDFs", "Images"],
            "dry_run": True,
        }
    }
    client = FakeLLMClient(response=response)
    result = parse_natural_language_request(client, "Organize the folder")

    assert isinstance(result.organize_request, OrganizeRequest)
    assert result.organize_request.categories == ["PDFs", "Images"]
    assert result.organize_request.dry_run is True


def test_parse_natural_language_request_rejects_extra_fields() -> None:
    response = {
        "organize_request": {
            "target_dir": ".",
            "categories": ["PDFs"],
            "dry_run": True,
            "extra_field": "not allowed",
        },
        "unexpected": True,
    }
    client = FakeLLMClient(response=response)
    with pytest.raises(ValueError, match="LLM response validation failed"):
        parse_natural_language_request(client, "Organize the folder")


def test_parse_natural_language_request_rejects_unsupported_categories() -> None:
    response = {
        "organize_request": {
            "target_dir": ".",
            "categories": ["PDFs", "UnknownCategory"],
            "dry_run": True,
        }
    }
    client = FakeLLMClient(response=response)
    with pytest.raises(ValueError, match="Unsupported categories"):
        parse_natural_language_request(client, "Organize the folder")
