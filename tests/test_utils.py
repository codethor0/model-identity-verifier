"""Tests for utilities."""

from model_identity_verifier.utils.helpers import redact_secrets


def test_secrets_redacted() -> None:
    text = "Error with key sk-abcdefghijklmnopqrstuvwxyz123456"
    redacted = redact_secrets(text)
    assert "sk-abc" not in redacted
    assert "[REDACTED]" in redacted
