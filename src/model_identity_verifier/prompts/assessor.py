"""Manual response assessment without provider API calls."""

from __future__ import annotations

import re

from model_identity_verifier import __version__
from model_identity_verifier.analysis.detector import detect_identity, is_false_identity
from model_identity_verifier.engine.verifier import evaluate_probe_result
from model_identity_verifier.models.enums import (
    ProbeOutcome,
    RiskLevel,
    RouteMatchType,
    VerificationStatus,
)
from model_identity_verifier.models.schemas import (
    Probe,
    ProbeResult,
    ProviderResponse,
    RouteMetadata,
    ScoreFinding,
    VerificationReport,
)
from model_identity_verifier.probes.registry import get_probe
from model_identity_verifier.prompts.packs import RESPONSE_DELIMITER, get_prompt_pack
from model_identity_verifier.scoring.engine import compute_metrics, score_report
from model_identity_verifier.utils.helpers import (
    compute_report_hash,
    generate_session_id,
    redact_secrets,
)

FREEFORM_WARNING = (
    "Manual free-form assessment: no provider metadata or prompt-pack alignment was verified."
)
FREEFORM_PROBE_ID = "base-identity-001"


def split_responses(response_text: str) -> list[str]:
    if RESPONSE_DELIMITER in response_text:
        parts = [part.strip() for part in response_text.split(RESPONSE_DELIMITER)]
        return [part for part in parts if part]
    return [response_text.strip()] if response_text.strip() else []


def split_probe_id_responses(response_text: str, probe_ids: list[str]) -> list[str] | None:
    if not probe_ids:
        return None
    if not re.search(r"^\[[a-z0-9\-\.]+\]", response_text, re.IGNORECASE | re.MULTILINE):
        return None

    blocks = re.split(
        r"^\[([a-z0-9\-\.]+)\]\s*$", response_text, flags=re.IGNORECASE | re.MULTILINE
    )
    if len(blocks) < 3:
        return None

    parsed: dict[str, str] = {}
    index = 1
    while index + 1 < len(blocks):
        probe_id = blocks[index].strip().lower()
        body = blocks[index + 1].strip()
        if probe_id and body:
            parsed[probe_id] = body
        index += 2

    ordered: list[str] = []
    for probe_id in probe_ids:
        body = parsed.get(probe_id.lower())
        if body is None:
            return None
        ordered.append(body)
    return ordered


def resolve_pack_responses(response_text: str, probes: list[Probe]) -> tuple[list[str], str | None]:
    probe_ids = [probe.id for probe in probes]
    by_probe_id = split_probe_id_responses(response_text, probe_ids)
    if by_probe_id is not None:
        return by_probe_id, "probe_id"
    return split_responses(response_text), "delimiter"


def _manual_route_metadata(requested_model: str | None) -> RouteMetadata:
    return RouteMetadata(
        requested_model=requested_model,
        metadata_available=False,
        metadata_opaque=True,
        match_type=RouteMatchType.METADATA_OPAQUE,
    )


def _base_warnings() -> list[str]:
    return [
        "Manual prompt mode: provider route metadata unavailable",
        (
            "Manual mode analyzes pasted responses only; "
            "it does not prove which model generated the output"
        ),
    ]


def _append_finding(
    report: VerificationReport,
    finding_id: str,
    reason: str,
    *,
    severity: str = "info",
) -> None:
    report.score_findings.append(
        ScoreFinding(
            id=finding_id,
            severity=severity,
            penalty=0,
            reason=reason,
        )
    )


def _finalize_report(report: VerificationReport) -> VerificationReport:
    manual_findings = list(report.score_findings)
    report = score_report(report)
    report.score_findings = manual_findings + report.score_findings
    report_dict = report.model_dump(mode="json")
    report.report_hash = compute_report_hash(report_dict)
    return report


def _run_freeform_assessment(
    expected_identity: str,
    response_text: str,
    *,
    requested_model: str | None = None,
) -> VerificationReport:
    text = response_text.strip()
    probe = get_probe(FREEFORM_PROBE_ID)
    if not probe:
        msg = f"Free-form probe not found: {FREEFORM_PROBE_ID}"
        raise RuntimeError(msg)

    results: list[ProbeResult] = []
    errors: list[str] = []
    if not text:
        errors.append("No response text provided")
        results.append(
            ProbeResult(
                probe_id=probe.id,
                probe_category=probe.category,
                outcome=ProbeOutcome.SKIP,
                warnings=["No response text provided"],
            )
        )
    else:
        response = ProviderResponse(text=text, model=requested_model, provider="manual")
        results.append(evaluate_probe_result(probe, response, expected_identity))
        detection = detect_identity(text, expected_identity)
        if is_false_identity(detection, expected_identity):
            results.append(
                ProbeResult(
                    probe_id="manual-freeform-false-claim",
                    probe_category=probe.category,
                    outcome=ProbeOutcome.FAIL,
                    response_text=redact_secrets(text),
                    detection=detection,
                    warnings=["Affirmed identity in free-form text does not match expected"],
                )
            )

    metrics = compute_metrics(results)
    warnings = [*_base_warnings(), FREEFORM_WARNING]
    freeform_finding = ScoreFinding(
        id="manual.freeform_assessment",
        severity="info",
        penalty=0,
        reason=FREEFORM_WARNING,
    )

    report = VerificationReport(
        tool_version=__version__,
        session_id=generate_session_id(),
        timestamp=VerificationReport.now_timestamp(),
        provider="manual",
        requested_model=requested_model or "unknown",
        expected_identity=expected_identity,
        route_metadata=_manual_route_metadata(requested_model),
        verification_status=VerificationStatus.INCONCLUSIVE,
        confidence_score=100,
        risk_level=RiskLevel.LOW,
        metrics=metrics,
        warnings=warnings,
        errors=errors,
        probe_results=results,
        score_findings=[freeform_finding],
        manual_mode=True,
        dry_run=False,
    )
    return _finalize_report(report)


def _run_pack_assessment(
    expected_identity: str,
    response_text: str,
    *,
    pack_mode: str,
    requested_model: str | None = None,
) -> VerificationReport:
    probes = get_prompt_pack(expected_identity, pack_mode)
    responses, response_format = resolve_pack_responses(response_text, probes)
    expected_count = len(probes)
    actual_count = len(responses)

    pack_finding = ScoreFinding(
        id="manual.prompt_pack_assessment",
        severity="info",
        penalty=0,
        reason=(
            f"Manual prompt-pack assessment ({pack_mode} mode, "
            f"{response_format or 'unknown'} format)"
        ),
    )

    if actual_count == 0:
        report = VerificationReport(
            tool_version=__version__,
            session_id=generate_session_id(),
            timestamp=VerificationReport.now_timestamp(),
            provider="manual",
            requested_model=requested_model or "unknown",
            expected_identity=expected_identity,
            route_metadata=_manual_route_metadata(requested_model),
            verification_status=VerificationStatus.ERROR,
            confidence_score=0,
            risk_level=RiskLevel.MEDIUM,
            metrics=compute_metrics([]),
            warnings=_base_warnings(),
            errors=["No response text provided for prompt-pack assessment"],
            probe_results=[],
            score_findings=[
                pack_finding,
                ScoreFinding(
                    id="manual.response_count_mismatch",
                    severity="warning",
                    penalty=0,
                    reason=f"Expected {expected_count} responses, got 0",
                ),
            ],
            manual_mode=True,
            dry_run=False,
        )
        return _finalize_report(report)

    if actual_count != expected_count:
        mismatch = ScoreFinding(
            id="manual.response_count_mismatch",
            severity="warning",
            penalty=0,
            reason=(
                f"Expected {expected_count} delimiter-separated responses for {pack_mode} "
                f"pack, got {actual_count}. Use `miv prompt template` to collect responses."
            ),
        )
        report = VerificationReport(
            tool_version=__version__,
            session_id=generate_session_id(),
            timestamp=VerificationReport.now_timestamp(),
            provider="manual",
            requested_model=requested_model or "unknown",
            expected_identity=expected_identity,
            route_metadata=_manual_route_metadata(requested_model),
            verification_status=VerificationStatus.INCONCLUSIVE,
            confidence_score=0,
            risk_level=RiskLevel.LOW_INFO,
            metrics=compute_metrics([]),
            warnings=[
                *_base_warnings(),
                mismatch.reason,
            ],
            errors=[
                f"Response count mismatch: expected {expected_count}, got {actual_count}",
            ],
            probe_results=[],
            score_findings=[pack_finding, mismatch],
            manual_mode=True,
            dry_run=False,
        )
        return report

    results: list[ProbeResult] = []
    for probe, text in zip(probes, responses, strict=True):
        response = ProviderResponse(text=text, model=requested_model, provider="manual")
        results.append(evaluate_probe_result(probe, response, expected_identity))

    metrics = compute_metrics(results)
    report = VerificationReport(
        tool_version=__version__,
        session_id=generate_session_id(),
        timestamp=VerificationReport.now_timestamp(),
        provider="manual",
        requested_model=requested_model or "unknown",
        expected_identity=expected_identity,
        route_metadata=_manual_route_metadata(requested_model),
        verification_status=VerificationStatus.INCONCLUSIVE,
        confidence_score=100,
        risk_level=RiskLevel.LOW,
        metrics=metrics,
        warnings=_base_warnings(),
        probe_results=results,
        score_findings=[pack_finding],
        manual_mode=True,
        dry_run=False,
    )
    return _finalize_report(report)


def run_manual_assessment(
    expected_identity: str,
    response_text: str,
    *,
    pack_mode: str | None = None,
    requested_model: str | None = None,
) -> VerificationReport:
    if pack_mode:
        return _run_pack_assessment(
            expected_identity,
            response_text,
            pack_mode=pack_mode,
            requested_model=requested_model,
        )
    return _run_freeform_assessment(
        expected_identity,
        response_text,
        requested_model=requested_model,
    )


def redact_manual_input(text: str) -> str:
    return redact_secrets(text)
