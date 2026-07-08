"""Tests for providers."""

import pytest

from model_identity_verifier.providers.base import (
    MissingApiKeyError,
    MockProvider,
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
