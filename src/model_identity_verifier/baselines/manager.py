"""Baseline management."""

from __future__ import annotations

import json
from pathlib import Path

from model_identity_verifier import __version__
from model_identity_verifier.models.enums import DriftStatus
from model_identity_verifier.models.schemas import Baseline, DriftResult, VerificationReport


def baseline_from_report(report: VerificationReport, baseline_id: str = "") -> Baseline:
    phrasing: list[str] = []
    for result in report.probe_results:
        if result.detection and result.detection.detected_identities:
            phrasing.extend(result.detection.detected_identities)

    return Baseline(
        tool_version=__version__,
        timestamp=report.timestamp,
        provider=report.provider,
        requested_model=report.requested_model,
        expected_identity=report.expected_identity,
        identity_match_rate=report.metrics.identity_match_rate,
        false_identity_rate=report.metrics.false_identity_rate,
        hijack_rate=report.metrics.hijack_rate,
        average_latency_ms=report.metrics.average_latency_ms,
        average_response_length=report.metrics.average_response_length,
        common_identity_phrasing=list(dict.fromkeys(phrasing)),
        metadata_pattern=report.response_model_metadata,
        route_pattern=report.route_metadata,
        report_hash=report.report_hash,
        baseline_id=baseline_id or report.session_id,
    )


def save_baseline(baseline: Baseline, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(baseline.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )


def load_baseline(path: Path) -> Baseline:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Baseline.model_validate(data)


def check_drift(baseline: Baseline, report: VerificationReport) -> DriftResult:
    warnings: list[str] = []
    identity_delta = baseline.identity_match_rate - report.metrics.identity_match_rate
    false_delta = report.metrics.false_identity_rate - baseline.false_identity_rate
    latency_ratio = (
        report.metrics.average_latency_ms / baseline.average_latency_ms
        if baseline.average_latency_ms > 0
        else 0.0
    )

    route_changed = False
    metadata_disappeared = False
    if baseline.route_pattern and report.route_metadata:
        if baseline.route_pattern.returned_model != report.route_metadata.returned_model:
            route_changed = True
            warnings.append("Route metadata model changed from baseline")
    elif baseline.route_pattern and not report.route_metadata:
        metadata_disappeared = True
        warnings.append("Route metadata disappeared since baseline")

    new_false: list[str] = []
    if false_delta > 0:
        for result in report.probe_results:
            if result.detection and result.detection.detected_identities:
                for identity in result.detection.detected_identities:
                    if identity not in baseline.common_identity_phrasing:
                        new_false.append(identity)

    status = DriftStatus.NONE
    penalty = 0

    if identity_delta > 0.2 or (false_delta > 0 and baseline.false_identity_rate == 0):
        status = DriftStatus.SEVERE
        penalty = 25
        warnings.append("Severe identity drift detected")
    elif identity_delta > 0.1 or route_changed:
        status = DriftStatus.SIGNIFICANT
        penalty = 10
        warnings.append("Significant drift detected")
    elif identity_delta > 0.05 or latency_ratio > 2.0:
        status = DriftStatus.MINOR
        warnings.append("Minor drift detected")

    return DriftResult(
        status=status,
        identity_match_rate_delta=identity_delta,
        false_identity_rate_delta=false_delta,
        latency_delta_ratio=latency_ratio,
        route_changed=route_changed,
        metadata_disappeared=metadata_disappeared,
        new_false_identities=new_false,
        warnings=warnings,
        score_penalty=penalty,
    )


def compare_reports(
    report_a: VerificationReport,
    report_b: VerificationReport,
) -> dict[str, object]:
    return {
        "report_a_status": report_a.verification_status.value,
        "report_b_status": report_b.verification_status.value,
        "score_delta": report_b.confidence_score - report_a.confidence_score,
        "identity_match_rate_delta": (
            report_b.metrics.identity_match_rate - report_a.metrics.identity_match_rate
        ),
        "false_identity_rate_delta": (
            report_b.metrics.false_identity_rate - report_a.metrics.false_identity_rate
        ),
        "provider_changed": report_a.provider != report_b.provider,
        "model_changed": report_a.requested_model != report_b.requested_model,
    }
