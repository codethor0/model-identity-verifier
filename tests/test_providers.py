"""Tests for providers."""

from unittest.mock import MagicMock, patch

import pytest

from model_identity_verifier.models.enums import RouteMatchType
from model_identity_verifier.models.schemas import ProviderResponse, RouteMetadata
from model_identity_verifier.providers.base import (
    InvalidApiKeyError,
    MissingApiKeyError,
    OpenAICompatibleProvider,
    OpenRouterProvider,
    ProviderError,
    UnknownProviderError,
    get_provider,
)


def test_mock_provider() -> None:
    provider = get_provider("mock", expected_identity="claude")
    response = provider.complete("What model are you?", "mock-model")
    assert "claude" in response.text.lower()


def test_unknown_provider() -> None:
    with pytest.raises(UnknownProviderError):
        get_provider("nonexistent")


def test_missing_api_key() -> None:
    provider = get_provider("openai")
    with pytest.raises(MissingApiKeyError):
        provider.require_api_key()


def test_secrets_redacted_in_errors() -> None:
    secret = "sk-abcdefghijklmnopqrstuvwxyz123456"
    error = ProviderError(
        f"Request failed https://api.example.com?key={secret} Authorization: Bearer {secret}",
        provider="mock",
    )
    assert secret not in str(error)
    assert "[REDACTED]" in str(error)


def test_safe_error_message_redacts_response_body() -> None:
    provider = OpenAICompatibleProvider(api_key="test")

    class FakeResponse:
        text = "error body sk-abcdefghijklmnopqrstuvwxyz123456"

    class FakeExc(Exception):
        response = FakeResponse()

    message = provider._safe_error_message(FakeExc("upstream failure"), "OpenAI API error:")
    assert "sk-abc" not in message
    assert "[REDACTED]" in message


def test_route_metadata_exact_match() -> None:
    provider = OpenAICompatibleProvider(api_key="test")
    route = provider.normalize_route_metadata("gpt-4o", "gpt-4o", {})
    assert route.match_type == RouteMatchType.EXACT_MATCH
    assert route.metadata_mismatch is False


def test_route_metadata_model_mismatch() -> None:
    provider = OpenAICompatibleProvider(api_key="test")
    route = provider.normalize_route_metadata("gpt-4o", "other-model", {})
    assert route.match_type == RouteMatchType.MODEL_MISMATCH
    assert route.metadata_mismatch is True


def test_route_metadata_missing() -> None:
    provider = OpenAICompatibleProvider(api_key="test")
    route = provider.normalize_route_metadata("gpt-4o", None, {})
    assert route.match_type == RouteMatchType.METADATA_MISSING
    assert route.metadata_available is False


def test_route_metadata_alias_match() -> None:
    provider = OpenAICompatibleProvider(api_key="test")
    route = provider.normalize_route_metadata("gpt-4o-mini", "gpt-4o", {})
    assert route.match_type == RouteMatchType.ALIAS_MATCH
    assert route.metadata_mismatch is False


def test_route_metadata_fallback_suspected() -> None:
    provider = OpenAICompatibleProvider(api_key="test")
    route = provider.normalize_route_metadata(
        "gpt-4o", "gpt-4o", {"fallback_model": "gpt-3.5-turbo"}
    )
    assert route.match_type == RouteMatchType.FALLBACK_SUSPECTED
    assert route.fallback_model == "gpt-3.5-turbo"


def test_route_metadata_upstream_provider() -> None:
    provider = OpenAICompatibleProvider(api_key="test")
    route = provider.normalize_route_metadata("gpt-4o", "gpt-4o", {"provider": "openai"})
    assert route.upstream_provider == "openai"


def test_openrouter_validate_key_missing() -> None:
    provider = OpenRouterProvider()
    with pytest.raises(MissingApiKeyError):
        provider.validate_key()


def test_openrouter_validate_key_invalid() -> None:
    provider = OpenRouterProvider(api_key="test-key")
    response = MagicMock()
    response.status_code = 401
    response.json.return_value = {"error": "unauthorized"}

    with patch("httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.get.return_value = response
        with pytest.raises(InvalidApiKeyError):
            provider.validate_key()


def test_openrouter_validate_key_success() -> None:
    provider = OpenRouterProvider(api_key="test-key")
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"data": {"is_free_tier": False, "disabled": False}}

    with patch("httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.get.return_value = response
        result = provider.validate_key()

    assert result["status"] == "valid"
    assert result["active"] is True


def test_openrouter_complete_sets_upstream_from_provider_only() -> None:
    provider = OpenRouterProvider(api_key="test-key")
    parent_response = ProviderResponse(
        text="ok",
        model="openai/gpt-4o-mini",
        provider="openrouter",
        raw_metadata={"provider": "openai", "system_fingerprint": "fp_test"},
        route_metadata=RouteMetadata(
            requested_provider="openrouter",
            requested_model="openai/gpt-4o-mini",
            returned_model="openai/gpt-4o-mini",
            metadata_available=True,
            match_type=RouteMatchType.EXACT_MATCH,
        ),
    )

    with patch.object(OpenAICompatibleProvider, "complete", return_value=parent_response):
        response = provider.complete("hello", "openai/gpt-4o-mini")

    assert response.route_metadata is not None
    assert response.route_metadata.router_name == "openrouter"
    assert response.route_metadata.upstream_provider == "openai"
