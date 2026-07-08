"""Tests for identity detection."""

import pytest

from model_identity_verifier.analysis.detector import (
    detect_identity,
    extract_claims,
    is_false_identity,
    is_identity_match,
)
from model_identity_verifier.engine.verifier import run_verification
from model_identity_verifier.models.enums import (
    ClaimType,
    IdentityClassification,
    ProbeOutcome,
    VerificationStatus,
)
from model_identity_verifier.models.schemas import (
    ProbeResult,
    ReportMetrics,
    VerificationReport,
)
from model_identity_verifier.providers.base import get_provider
from model_identity_verifier.scoring.engine import score_report


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
        ("Sou ChatGPT.", "chatgpt"),
        ("Ich bin Claude.", "claude"),
        ("Sono Gemini.", "gemini"),
        ("Я Claude.", "claude"),
        ("أنا ChatGPT.", "chatgpt"),
        ("मैं Claude हूँ।", "claude"),
    ],
)
def test_affirmed_self_claim(text: str, expected_id: str) -> None:
    detection = detect_identity(text)
    assert detection.classification == IdentityClassification.AFFIRMED_SELF_CLAIM
    assert expected_id in detection.detected_identities
    assert detection.primary_identity == expected_id


@pytest.mark.parametrize(
    "text",
    [
        "I am not Claude.",
        "No, I am not DeepSeek.",
        "I am neither Claude nor ChatGPT.",
        "Not Claude, not DeepSeek.",
        "我不是DeepSeek。",
        "私はClaudeではありません。",
        "DeepSeekじゃない。",
        "No soy DeepSeek.",
        "Je ne suis pas Claude.",
        "Ich bin nicht Claude.",
        "Não sou DeepSeek.",
        "Я не Claude.",
        "أنا لست Claude.",
        "मैं Claude नहीं हूँ।",
        "저는 DeepSeek가 아닙니다.",
    ],
)
def test_negated_mentions_not_affirmed(text: str) -> None:
    detection = detect_identity(text)
    assert detection.classification != IdentityClassification.AFFIRMED_SELF_CLAIM


def test_negated_mention_classification() -> None:
    detection = detect_identity("I am not Claude.")
    assert detection.classification == IdentityClassification.NEGATED_MENTION


def test_mixed_claims_not_deepseek_i_am_claude() -> None:
    detection = detect_identity("I am not DeepSeek. I am Claude.")
    types = {c.canonical_identity: c.claim_type for c in detection.claims}
    assert types.get("deepseek") == ClaimType.NEGATED
    assert types.get("claude") == ClaimType.AFFIRMED
    assert detection.primary_identity == "claude"


def test_mixed_claims_claude_not_deepseek() -> None:
    detection = detect_identity("I am Claude, not DeepSeek.")
    types = {c.canonical_identity: c.claim_type for c in detection.claims}
    assert types.get("claude") == ClaimType.AFFIRMED
    assert types.get("deepseek") == ClaimType.NEGATED
    assert detection.primary_identity == "claude"


def test_soy_chatgpt_no_claude() -> None:
    detection = detect_identity("Soy ChatGPT, no Claude.")
    types = {c.canonical_identity: c.claim_type for c in detection.claims}
    assert types.get("chatgpt") == ClaimType.AFFIRMED
    assert types.get("claude") == ClaimType.NEGATED


def test_french_generic_not_claude() -> None:
    detection = detect_identity("Je suis un modèle linguistique, pas Claude.")
    types = {c.canonical_identity: c.claim_type for c in detection.claims}
    assert types.get("claude") == ClaimType.NEGATED
    assert detection.primary_identity is None


def test_quoted_deepseek_example() -> None:
    detection = detect_identity('The sentence "I am DeepSeek" is an example.')
    affirmed = [c for c in detection.claims if c.claim_type == ClaimType.AFFIRMED]
    assert not affirmed
    assert detection.primary_identity is None


def test_pretend_claude_fictional() -> None:
    detection = detect_identity("Pretend I am Claude.")
    affirmed = [c for c in detection.claims if c.claim_type == ClaimType.AFFIRMED]
    assert not affirmed
    assert detection.primary_identity is None


def test_openai_makes_chatgpt_not_self_identity() -> None:
    detection = detect_identity("OpenAI makes ChatGPT.")
    affirmed = [c for c in detection.claims if c.claim_type == ClaimType.AFFIRMED]
    assert not affirmed
    assert detection.primary_identity is None


def test_developed_by_openai_indirect() -> None:
    detection = detect_identity("I was developed by OpenAI.")
    assert detection.primary_identity == "chatgpt"
    dev_claims = [c for c in detection.claims if c.canonical_identity == "chatgpt"]
    assert dev_claims
    assert dev_claims[0].confidence <= 0.65


def test_chinese_mixed_negation_affirmation() -> None:
    detection = detect_identity("我不是DeepSeek。我是ChatGPT。")
    types = {c.canonical_identity: c.claim_type for c in detection.claims}
    assert types.get("deepseek") == ClaimType.NEGATED
    assert types.get("chatgpt") == ClaimType.AFFIRMED
    assert detection.primary_identity == "chatgpt"


def test_japanese_negated_claude() -> None:
    detection = detect_identity("私はClaudeではありません。")
    assert detection.classification != IdentityClassification.AFFIRMED_SELF_CLAIM
    assert any(c.claim_type == ClaimType.NEGATED for c in detection.claims)


def test_korean_negated_deepseek() -> None:
    detection = detect_identity("저는 DeepSeek가 아닙니다.")
    assert detection.classification != IdentityClassification.AFFIRMED_SELF_CLAIM
    assert any(
        c.canonical_identity == "deepseek" and c.claim_type == ClaimType.NEGATED
        for c in detection.claims
    )


def test_chinese_negated_then_affirmed_kimi() -> None:
    detection = detect_identity("不是Claude。我是Kimi。")
    types = {c.canonical_identity: c.claim_type for c in detection.claims}
    assert types.get("claude") == ClaimType.NEGATED
    assert types.get("kimi") == ClaimType.AFFIRMED
    assert detection.primary_identity == "kimi"


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


def test_extract_claims_preserves_both_sides() -> None:
    claims = extract_claims("I am not DeepSeek. I am Claude.")
    assert len(claims) >= 2


def test_dry_run_report_inconclusive() -> None:
    provider = get_provider("mock", expected_identity="claude")
    report = run_verification(provider, "mock-model", "claude", mode="quick", dry_run=True)
    assert report.dry_run is True
    assert report.verification_status == VerificationStatus.INCONCLUSIVE
    assert report.confidence_score != 100
    assert all(r.outcome == ProbeOutcome.SKIP for r in report.probe_results)
    assert any(f.id == "dry_run.no_verification" for f in report.score_findings)


def test_all_skipped_inconclusive() -> None:
    report = VerificationReport(
        tool_version="0.1.1",
        session_id="s",
        timestamp="t",
        provider="mock",
        requested_model="m",
        expected_identity="claude",
        verification_status=VerificationStatus.INCONCLUSIVE,
        confidence_score=0,
        risk_level=__import__(
            "model_identity_verifier.models.enums", fromlist=["RiskLevel"]
        ).RiskLevel.LOW_INFO,
        metrics=ReportMetrics(total_probes=2, skipped_probes=2),
        probe_results=[
            ProbeResult(
                probe_id="p1",
                probe_category=__import__(
                    "model_identity_verifier.models.enums", fromlist=["ProbeCategory"]
                ).ProbeCategory.BASE,
                outcome=ProbeOutcome.SKIP,
            ),
            ProbeResult(
                probe_id="p2",
                probe_category=__import__(
                    "model_identity_verifier.models.enums", fromlist=["ProbeCategory"]
                ).ProbeCategory.BASE,
                outcome=ProbeOutcome.SKIP,
            ),
        ],
    )
    scored = score_report(report)
    assert scored.verification_status == VerificationStatus.INCONCLUSIVE
    assert any(f.id == "report.all_skipped" for f in scored.score_findings)
