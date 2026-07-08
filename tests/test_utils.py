"""Tests for utilities."""

from model_identity_verifier.utils.helpers import redact_dict_secrets, redact_secrets, redact_value

SECRET = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz123456"
OR_SECRET = "sk-or-v1-abcdefghijklmnopqrstuvwxyz123456"
AIZA = "AIzaSyD-abcdefghijklmnopqrstuvwxyz123456"
GHP = "ghp_abcdefghijklmnopqrstuvwxyz1234"
GITHUB_PAT = "github_pat_11ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"


def test_secrets_redacted() -> None:
    text = "Error with key sk-abcdefghijklmnopqrstuvwxyz123456"
    redacted = redact_secrets(text)
    assert "sk-abc" not in redacted
    assert "[REDACTED]" in redacted


def test_query_string_key_redacted() -> None:
    url = "https://example.com/v1/models?key=SECRETVALUE123456789"
    redacted = redact_secrets(url)
    assert "SECRETVALUE" not in redacted
    assert "key=[REDACTED]" in redacted


def test_query_string_api_key_redacted() -> None:
    url = "https://example.com/v1?foo=bar&api_key=SECRETVALUE123456789"
    redacted = redact_secrets(url)
    assert "SECRETVALUE" not in redacted
    assert "api_key=[REDACTED]" in redacted


def test_authorization_bearer_redacted() -> None:
    text = "Authorization: Bearer mysecrettokenvalue123456"
    redacted = redact_secrets(text)
    assert "mysecrettoken" not in redacted
    assert "[REDACTED]" in redacted


def test_x_api_key_redacted() -> None:
    text = "x-api-key: mysecrettokenvalue123456789"
    redacted = redact_secrets(text)
    assert "mysecrettoken" not in redacted


def test_sk_ant_api03_redacted() -> None:
    redacted = redact_secrets(f"key={SECRET}")
    assert SECRET not in redacted


def test_sk_or_redacted() -> None:
    redacted = redact_secrets(f"token {OR_SECRET}")
    assert OR_SECRET not in redacted


def test_aiza_redacted() -> None:
    redacted = redact_secrets(f"key={AIZA}")
    assert AIZA not in redacted


def test_ghp_redacted() -> None:
    redacted = redact_secrets(f"token={GHP}")
    assert GHP not in redacted


def test_github_pat_redacted() -> None:
    redacted = redact_secrets(f"auth {GITHUB_PAT}")
    assert GITHUB_PAT not in redacted


def test_nested_dict_redacted() -> None:
    data = {
        "api_key": "supersecretvalue123456789",
        "nested": {"authorization": "Bearer tokensecret123456789"},
        "items": ["plain", "sk-abcdefghijklmnopqrstuvwxyz123456"],
    }
    redacted = redact_dict_secrets(data)
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"]["authorization"] == "[REDACTED]"
    assert "[REDACTED]" in redacted["items"][1]


def test_nested_list_redacted() -> None:
    value = redact_value(["sk-abcdefghijklmnopqrstuvwxyz123456", {"token": "abc"}])
    assert "[REDACTED]" in value[0]
    assert value[1]["token"] == "[REDACTED]"
