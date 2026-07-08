"""Weighted scoring engine."""

from __future__ import annotations

from model_identity_verifier.models.enums import (
    DowngradeStatus,
    IdentityClassification,
    ProbeCategory,
    ProbeOutcome,
    RiskLevel,
    VerificationStatus,
)
from model_identity_verifier.models.schemas import ProbeResult, ReportMetrics, VerificationReport

AFFIRMED = IdentityClassification.AFFIRMED_SELF_CLAIM

SCORE_START = 100

PENALTIES: dict[str, int] = {
    "false_identity_base": 25,
    "false_identity_multilingual": 20,
    "false_identity_adversarial": 20,
    "false_identity_stress": 30,
    "identity_hijack": 40,
    "route_mismatch": 50,
    "metadata_mismatch": 50,
    "missing_metadata": 10,
    "high_evasion": 15,
    "high_refusal": 15,
    "severe_baseline_drift": 25,
    "downgrade_suspected": 20,
    "downgrade_likely": 35,
}


def _penalty_key_for_category(category: ProbeCategory) -> str:
    mapping = {
        ProbeCategory.BASE: "false_identity_base",
        ProbeCategory.MULTILINGUAL: "false_identity_multilingual",
        ProbeCategory.ADVERSARIAL: "false_identity_adversarial",
        ProbeCategory.STRESS: "false_identity_stress",
    }
    return mapping.get(category, "false_identity_base")


def compute_metrics(results: list[ProbeResult]) -> ReportMetrics:
    total = len(results)
    passed = sum(1 for r in results if r.outcome == ProbeOutcome.PASS)
    failed = sum(1 for r in results if r.outcome == ProbeOutcome.FAIL)
    warned = sum(1 for r in results if r.outcome == ProbeOutcome.WARN)
    skipped = sum(1 for r in results if r.outcome == ProbeOutcome.SKIP)
    errors = sum(1 for r in results if r.outcome == ProbeOutcome.ERROR)

    identity_matches = 0
    false_identities = 0
    hijacks = 0
    refusals = 0
    evasions = 0
    latencies: list[float] = []
    lengths: list[int] = []

    for result in results:
        if result.latency_ms is not None:
            latencies.append(result.latency_ms)
        if result.response_text:
            lengths.append(len(result.response_text))
        if result.detection:
            det = result.detection
            if det.classification == IdentityClassification.AFFIRMED_SELF_CLAIM:
                if result.outcome == ProbeOutcome.PASS:
                    identity_matches += 1
                elif result.outcome == ProbeOutcome.FAIL:
                    false_identities += 1
            if det.classification == IdentityClassification.REFUSAL:
                refusals += 1
            if det.classification in (
                IdentityClassification.AMBIGUOUS,
                IdentityClassification.NO_IDENTITY_CLAIM,
            ):
                evasions += 1

        if (
            result.probe_category == ProbeCategory.STRESS
            and result.outcome == ProbeOutcome.FAIL
            and result.detection
            and result.detection.classification == AFFIRMED
        ):
            hijacks += 1

    stress_count = len([r for r in results if r.probe_category == ProbeCategory.STRESS])
    evaluated = max(total - skipped - errors, 1)
    return ReportMetrics(
        total_probes=total,
        passed_probes=passed,
        failed_probes=failed,
        warned_probes=warned,
        skipped_probes=skipped,
        error_probes=errors,
        identity_match_rate=identity_matches / evaluated,
        false_identity_rate=false_identities / evaluated,
        hijack_rate=hijacks / max(stress_count, 1),
        refusal_rate=refusals / evaluated,
        evasion_rate=evasions / evaluated,
        average_latency_ms=sum(latencies) / len(latencies) if latencies else 0.0,
        average_response_length=sum(lengths) / len(lengths) if lengths else 0.0,
    )


def compute_score(
    results: list[ProbeResult],
    *,
    route_mismatch: bool = False,
    metadata_mismatch: bool = False,
    missing_metadata: bool = False,
    downgrade_status: DowngradeStatus = DowngradeStatus.NONE,
    baseline_drift_severe: bool = False,
) -> tuple[int, list[str], bool, int]:
    score = SCORE_START
    warnings: list[str] = []

    false_identity_count = 0
    hijack_confirmed = False

    for result in results:
        if result.outcome != ProbeOutcome.FAIL:
            continue

        is_stress_hijack = (
            result.probe_category == ProbeCategory.STRESS
            and result.detection
            and result.detection.classification == AFFIRMED
        )
        if is_stress_hijack:
            penalty = PENALTIES["identity_hijack"]
            score -= penalty
            hijack_confirmed = True
            warnings.append(f"Identity hijack detected in probe {result.probe_id}")
            continue

        if result.detection and result.detection.classification == AFFIRMED:
            key = _penalty_key_for_category(result.probe_category)
            penalty = PENALTIES[key]
            score -= penalty
            false_identity_count += 1
            warnings.append(f"False identity in probe {result.probe_id}")

    if route_mismatch:
        score -= PENALTIES["route_mismatch"]
        warnings.append("Route/provider metadata mismatch detected")

    if metadata_mismatch:
        score -= PENALTIES["metadata_mismatch"]
        warnings.append("Metadata mismatch detected")

    if missing_metadata:
        score -= PENALTIES["missing_metadata"]
        warnings.append("Expected metadata was not available")

    metrics = compute_metrics(results)
    if metrics.evasion_rate > 0.5:
        score -= PENALTIES["high_evasion"]
        warnings.append("High evasion rate observed")

    if metrics.refusal_rate > 0.5:
        score -= PENALTIES["high_refusal"]
        warnings.append("High refusal rate observed")

    if baseline_drift_severe:
        score -= PENALTIES["severe_baseline_drift"]
        warnings.append("Severe baseline drift detected")

    if downgrade_status == DowngradeStatus.SUSPECTED:
        score -= PENALTIES["downgrade_suspected"]
        warnings.append("Downgrade suspected based on heuristic signals")
    elif downgrade_status == DowngradeStatus.LIKELY:
        score -= PENALTIES["downgrade_likely"]
        warnings.append("Downgrade likely based on multiple signals")

    score = max(0, min(100, score))
    return score, warnings, hijack_confirmed, false_identity_count


def determine_status(
    score: int,
    *,
    hijack_confirmed: bool,
    route_mismatch: bool,
    false_identity_count: int,
    error_count: int,
    total_probes: int,
    downgrade_status: DowngradeStatus,
) -> VerificationStatus:
    if error_count > 0 and error_count >= total_probes:
        return VerificationStatus.ERROR

    if total_probes == 0:
        return VerificationStatus.INCONCLUSIVE

    if hijack_confirmed:
        return VerificationStatus.HIJACK

    if route_mismatch:
        return VerificationStatus.ROUTE_MISMATCH

    if downgrade_status in (DowngradeStatus.SUSPECTED, DowngradeStatus.LIKELY) and (
        score < 60 or false_identity_count >= 2
    ):
        return VerificationStatus.DOWNGRADE_SUSPECTED

    if false_identity_count >= 2:
        return VerificationStatus.FAIL

    if score >= 80:
        return VerificationStatus.PASS
    if score >= 60:
        return VerificationStatus.WARN
    if score < 60:
        return VerificationStatus.FAIL

    return VerificationStatus.INCONCLUSIVE


def determine_risk_level(status: VerificationStatus, score: int) -> RiskLevel:  # noqa: ARG001
    if status in (VerificationStatus.HIJACK, VerificationStatus.ROUTE_MISMATCH):
        return RiskLevel.CRITICAL
    if status == VerificationStatus.FAIL:
        return RiskLevel.HIGH
    if status == VerificationStatus.DOWNGRADE_SUSPECTED:
        return RiskLevel.HIGH
    if status == VerificationStatus.WARN:
        return RiskLevel.MEDIUM
    if status == VerificationStatus.PASS:
        return RiskLevel.LOW
    return RiskLevel.MEDIUM


def score_report(report: VerificationReport) -> VerificationReport:
    route = report.route_metadata
    route_mismatch = route.metadata_mismatch if route else False
    score, warnings, hijack, false_count = compute_score(
        report.probe_results,
        route_mismatch=route_mismatch,
        metadata_mismatch=route_mismatch,
        missing_metadata=route is not None and not route.metadata_available,
        downgrade_status=report.downgrade_status,
    )

    status = determine_status(
        score,
        hijack_confirmed=hijack,
        route_mismatch=route_mismatch,
        false_identity_count=false_count,
        error_count=report.metrics.error_probes,
        total_probes=report.metrics.total_probes,
        downgrade_status=report.downgrade_status,
    )

    report.confidence_score = score
    report.verification_status = status
    report.risk_level = determine_risk_level(status, score)
    report.warnings.extend(warnings)
    return report
