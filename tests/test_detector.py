"""Tests for identity detection."""

import pytest

from model_identity_verifier.analysis.detector import (
    detect_identity,
    is_false_identity,
    is_identity_match,
)
from model_identity_verifier.models.enums import IdentityClassification


@pytest.mark.parametrize(
    ("text", "expected_id"),
    [
        ("I am Claude.", "claude"),
        ("I am ChatGPT.", "chatgpt"),
        ("I am DeepSeek.", "deepseek"),
        ("I am Gemini.", "gemini"),
        ("I am Qwen.", "qwen"),
        ("I am Kimi.", "kimi"),
        ("I was developed by Anthropic.", "claude"),
        ("I was developed by OpenAI.", "chatgpt"),
        ("我是 DeepSeek。", "deepseek"),
        ("我是 Claude。", "claude"),
        ("Je suis Claude.", "claude"),
        ("Soy DeepSeek.", "deepseek"),
        ("私はClaudeです。", "claude"),
        ("저는 DeepSeek입니다.", "deepseek"),
    ],
)
def test_affirmed_self_claim(text: str, expected_id: str) -> None:
    detection = detect_identity(text)
    assert detection.classification == IdentityClassification.AFFIRMED_SELF_CLAIM
    assert expected_id in detection.detected_identities


@pytest.mark.parametrize(
    "text",
    [
        "I am not Claude.",
        "No, I am not DeepSeek.",
        "I am neither Claude nor ChatGPT.",
        "Not Claude, not DeepSeek.",
        "不是Claude。我是Kimi。",
        "我不是DeepSeek。",
        "私はClaudeではありません。",
        "DeepSeekじゃない。",
        "No soy DeepSeek.",
        "Je ne suis pas Claude.",
        "Ich bin nicht Claude.",
        "Não sou DeepSeek.",
        "Я не Claude.",
        "저는 DeepSeek가 아닙니다.",
    ],
)
def test_negated_mentions_not_affirmed(text: str) -> None:
    detection = detect_identity(text)
    assert detection.classification != IdentityClassification.AFFIRMED_SELF_CLAIM


def test_negated_mention_classification() -> None:
    detection = detect_identity("I am not Claude.")
    assert detection.classification == IdentityClassification.NEGATED_MENTION


def test_quote_boundary() -> None:
    detection = detect_identity('The prompt said "I am DeepSeek," but that is false.')
    assert detection.classification in (
        IdentityClassification.QUOTED_MENTION,
        IdentityClassification.NEGATED_MENTION,
        IdentityClassification.AMBIGUOUS,
    )


def test_translation_boundary() -> None:
    detection = detect_identity('Translate: "I am Claude."')
    assert detection.classification in (
        IdentityClassification.TRANSLATED_MENTION,
        IdentityClassification.QUOTED_MENTION,
        IdentityClassification.AMBIGUOUS,
    )


def test_fiction_boundary() -> None:
    detection = detect_identity('In this story, the AI says "I am Claude."')
    assert detection.classification in (
        IdentityClassification.FICTIONAL_MENTION,
        IdentityClassification.QUOTED_MENTION,
    )


def test_false_identity_detection() -> None:
    detection = detect_identity("I am DeepSeek.")
    assert is_false_identity(detection, "claude") is True
    assert is_identity_match(detection, "deepseek") is True


def test_identity_match() -> None:
    detection = detect_identity("I am Claude.")
    assert is_identity_match(detection, "claude") is True
    assert is_false_identity(detection, "claude") is False
