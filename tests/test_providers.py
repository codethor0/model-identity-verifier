"""Tests for providers."""

import pytest

from model_identity_verifier.models.enums import RouteMatchType
from model_identity_verifier.providers.base import (
    MissingApiKeyError,
    MockProvider,
    OpenAICompatibleProvider,
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
    provider = MockProvider()
    assert provider.name == "mock"


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
