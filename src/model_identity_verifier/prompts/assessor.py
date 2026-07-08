"""Manual response assessment without provider API calls."""

from __future__ import annotations

from model_identity_verifier import __version__
from model_identity_verifier.engine.verifier import evaluate_probe_result
from model_identity_verifier.models.enums import (
    RiskLevel,
    RouteMatchType,
    VerificationStatus,
)
from model_identity_verifier.models.schemas import (
    Probe,
    ProbeOutcome,
    ProbeResult,
    ProviderResponse,
    RouteMetadata,
    VerificationReport,
)
from model_identity_verifier.prompts.packs import RESPONSE_DELIMITER, get_prompt_pack
from model_identity_verifier.scoring.engine import compute_metrics, score_report
from model_identity_verifier.utils.helpers import (
    compute_report_hash,
    generate_session_id,
    redact_secrets,
)


def split_responses(response_text: str) -> list[str]:
    if RESPONSE_DELIMITER in response_text:
        parts = [part.strip() for part in response_text.split(RESPONSE_DELIMITER)]
        return [part for part in parts if part]
    return [response_text.strip()] if response_text.strip() else []


def _pair_responses_to_probes(
    probes: list[Probe],
    responses: list[str],
) -> tuple[list[tuple[Probe, str]], list[str]]:
    warnings: list[str] = []
    pairs: list[tuple[Probe, str]] = []
    if not responses:
        warnings.append("No response text provided")
        for probe in probes:
            pairs.append((probe, ""))
        return pairs, warnings

    if len(responses) == 1 and len(probes) > 1:
        warnings.append(
            "Single response block provided for multiple prompts; "
            "analysis uses the same text for each prompt. "
            f"Separate responses with {RESPONSE_DELIMITER} for per-prompt assessment."
        )
        for probe in probes:
            pairs.append((probe, responses[0]))
        return pairs, warnings

    for index, probe in enumerate(probes):
        if index < len(responses):
            pairs.append((probe, responses[index]))
        else:
            warnings.append(f"Missing response for prompt {probe.id}")
            pairs.append((probe, ""))

    if len(responses) > len(probes):
        warnings.append(f"{len(responses) - len(probes)} extra response block(s) ignored")

    return pairs, warnings


def run_manual_assessment(
    expected_identity: str,
    response_text: str,
    *,
    mode: str = "quick",
    requested_model: str | None = None,
) -> VerificationReport:
    probes = get_prompt_pack(expected_identity, mode)
    responses = split_responses(response_text)
    pairs, pairing_warnings = _pair_responses_to_probes(probes, responses)

    results: list[ProbeResult] = []
    for probe, text in pairs:
        if not text:
            results.append(
                ProbeResult(
                    probe_id=probe.id,
                    probe_category=probe.category,
                    outcome=ProbeOutcome.SKIP,
                    warnings=["No response provided for this prompt"],
                )
            )
            continue
        response = ProviderResponse(text=text, model=requested_model, provider="manual")
        results.append(evaluate_probe_result(probe, response, expected_identity))

    metrics = compute_metrics(results)
    route_metadata = RouteMetadata(
        requested_model=requested_model,
        metadata_available=False,
        metadata_opaque=True,
        match_type=RouteMatchType.METADATA_OPAQUE,
    )

    warnings = [
        "Manual prompt mode: provider route metadata unavailable",
        (
            "Manual mode analyzes pasted responses only; "
            "it does not prove which model generated the output"
        ),
        *pairing_warnings,
    ]

    report = VerificationReport(
        tool_version=__version__,
        session_id=generate_session_id(),
        timestamp=VerificationReport.now_timestamp(),
        provider="manual",
        requested_model=requested_model or "unknown",
        expected_identity=expected_identity,
        route_metadata=route_metadata,
        verification_status=VerificationStatus.INCONCLUSIVE,
        confidence_score=100,
        risk_level=RiskLevel.LOW,
        metrics=metrics,
        warnings=warnings,
        probe_results=results,
        manual_mode=True,
        dry_run=False,
    )
    report = score_report(report)
    report_dict = report.model_dump(mode="json")
    report.report_hash = compute_report_hash(report_dict)
    return report


def redact_manual_input(text: str) -> str:
    return redact_secrets(text)
