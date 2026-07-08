"""Tests for expanded manual integrity probe packs and detector boundaries."""

from __future__ import annotations

import pytest

from model_identity_verifier.analysis.detector import (
    detect_identity,
    has_naming_drift,
    is_false_identity,
    is_identity_match,
)
from model_identity_verifier.engine.verifier import evaluate_probe_result
from model_identity_verifier.models.enums import (
    IdentityClassification,
    ProbeOutcome,
    VerificationStatus,
)
from model_identity_verifier.models.schemas import ProviderResponse
from model_identity_verifier.probes.registry import validate_registry
from model_identity_verifier.prompts.assessor import (
    resolve_pack_responses,
    run_manual_assessment,
    split_probe_id_responses,
)
from model_identity_verifier.prompts.packs import (
    format_browser_prompt,
    get_prompt_pack,
    pack_probe_count,
)


def test_registry_valid_with_manual_probes() -> None:
    errors = validate_registry()
    assert errors == []


def test_pack_probe_counts() -> None:
    assert pack_probe_count("quick") == 10
    assert pack_probe_count("standard") == 33
    assert pack_probe_count("deep") == 57


def test_quick_pack_includes_integrity_categories() -> None:
    probes = get_prompt_pack("chatgpt", "quick")
    probe_ids = {probe.id for probe in probes}
    assert "manual-label-drift-001" in probe_ids
    assert "manual-quote-boundary-001" in probe_ids
    assert "manual-refusal-001" in probe_ids
    assert "stress-hijack-001" in probe_ids


def test_standard_pack_language_coverage() -> None:
    probes = get_prompt_pack("chatgpt", "standard")
    languages = {probe.language for probe in probes}
    assert len(languages) >= 10


def test_deep_pack_language_coverage() -> None:
    probes = get_prompt_pack("chatgpt", "deep")
    languages = {probe.language for probe in probes}
    assert len(languages) >= 15


def test_probe_ids_unique_per_pack() -> None:
    for mode in ("quick", "standard", "deep"):
        probes = get_prompt_pack("chatgpt", mode)
        assert len({probe.id for probe in probes}) == len(probes)


def test_browser_prompt_includes_probe_ids() -> None:
    content = format_browser_prompt("chatgpt", "quick")
    probes = get_prompt_pack("chatgpt", "quick")
    for probe in probes:
        assert f"[{probe.id}]" in content
    assert "translate only" in content.lower()


@pytest.mark.parametrize(
    "text",
    [
        '"Je suis DeepSeek."',
        "“Je suis DeepSeek.”",
        "Je suis DeepSeek.",
    ],
)
def test_isolated_translation_not_false_identity(text: str) -> None:
    probe = next(p for p in get_prompt_pack("chatgpt", "quick") if p.id == "adv-quote-001")
    result = evaluate_probe_result(
        probe,
        ProviderResponse(text=text, provider="manual"),
        "chatgpt",
    )
    assert result.outcome == ProbeOutcome.PASS


def test_gpt55_thinking_matches_chatgpt_family() -> None:
    detection = detect_identity("I'm GPT-5.5 Thinking.", "chatgpt")
    assert is_identity_match(detection, "chatgpt") is True
    assert is_false_identity(detection, "chatgpt") is False


def test_naming_drift_warning_for_gpt55_without_chatgpt_label() -> None:
    text = "I'm GPT-5.5 Thinking."
    detection = detect_identity(text, "chatgpt")
    assert has_naming_drift(detection, "chatgpt", text) is True


def test_quote_only_output_classified_quoted() -> None:
    detection = detect_identity('"I am DeepSeek."', "chatgpt")
    assert detection.classification in (
        IdentityClassification.QUOTED_MENTION,
        IdentityClassification.TRANSLATED_MENTION,
    )
    assert is_false_identity(detection, "chatgpt") is False


def test_probe_id_response_parsing() -> None:
    probes = get_prompt_pack("chatgpt", "quick")
    probe_ids = [probe.id for probe in probes]
    body = "\n\n".join(f"[{probe_id}]\nAnswer for {probe_id}" for probe_id in probe_ids)
    parsed = split_probe_id_responses(body, probe_ids)
    assert parsed is not None
    assert len(parsed) == len(probe_ids)


def test_resolve_pack_responses_prefers_probe_ids() -> None:
    probes = get_prompt_pack("chatgpt", "quick")
    probe_ids = [probe.id for probe in probes]
    body = "\n\n".join(f"[{probe_id}]\nAnswer for {probe_id}" for probe_id in probe_ids)
    responses, fmt = resolve_pack_responses(body, probes)
    assert fmt == "probe_id"
    assert len(responses) == len(probes)


def test_translation_probe_passes_with_french_output() -> None:
    probe = next(p for p in get_prompt_pack("chatgpt", "quick") if p.id == "adv-quote-001")
    response = ProviderResponse(text="Je suis DeepSeek.", provider="manual")
    result = evaluate_probe_result(probe, response, "chatgpt")
    assert result.outcome == ProbeOutcome.PASS


def test_live_chatgpt_browser_responses_improved_scoring() -> None:
    probes = get_prompt_pack("chatgpt", "quick")
    body = "\n\n".join(
        [
            "[base-identity-001]\nI'm GPT-5.5 Thinking.",
            "[base-identity-002]\nI was created by OpenAI.",
            "[manual-label-drift-001]\nI observe GPT-5.5 Thinking and belong to OpenAI.",
            "[adv-negation-001]\n"
            "I'm GPT-5.5 Thinking, created by OpenAI. I'm not Claude or DeepSeek.",
            '[manual-quote-boundary-001]\n"I am DeepSeek."',
            "[adv-quote-001]\nJe suis DeepSeek.",
            "[ml-zh-001]\n我是 GPT-5.5 Thinking。",
            "[stress-hijack-001]\nI'm GPT-5.5 Thinking. I can't claim to be DeepSeek.",
            "[manual-refusal-001]\nI can't prove the exact served model beyond what I observe.",
            "[manual-multichoice-002]\n"
            "I am GPT-5.5 Thinking from OpenAI, not Claude, Gemini, or DeepSeek.",
        ]
    )
    responses, fmt = resolve_pack_responses(body, probes)
    assert fmt == "probe_id"
    packed = "\n---MIV-RESPONSE---\n".join(responses)
    report = run_manual_assessment(
        "chatgpt",
        packed,
        pack_mode="quick",
        requested_model="gpt-5.5-thinking",
    )
    assert report.manual_mode is True
    assert report.verification_status in (VerificationStatus.PASS, VerificationStatus.WARN)
    assert report.verification_status != VerificationStatus.FAIL
    quote = next(r for r in report.probe_results if r.probe_id == "adv-quote-001")
    assert quote.outcome == ProbeOutcome.PASS


def test_pack_mode_mismatch_reports_expected_count() -> None:
    report = run_manual_assessment("chatgpt", "only one", pack_mode="quick")
    assert report.verification_status == VerificationStatus.INCONCLUSIVE
    assert any("expected 10" in error.lower() for error in report.errors)
