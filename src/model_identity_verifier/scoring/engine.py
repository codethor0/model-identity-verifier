"""Weighted scoring engine with structured findings."""

from __future__ import annotations

from model_identity_verifier.models.enums import (
    DowngradeStatus,
    IdentityClassification,
    ProbeCategory,
    ProbeOutcome,
    RiskLevel,
    RouteMatchType,
    VerificationStatus,
)
from model_identity_verifier.models.schemas import (
    ProbeResult,
    ReportMetrics,
    ScoreFinding,
    VerificationReport,
)

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
    "opaque_metadata": 10,
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


def _finding_id_for_penalty_key(key: str) -> str:
    mapping = {
        "false_identity_base": "identity.false_claim",
        "false_identity_multilingual": "identity.false_claim",
        "false_identity_adversarial": "identity.false_claim",
        "false_identity_stress": "identity.false_claim",
        "identity_hijack": "identity.hijack_suspected",
        "route_mismatch": "route.metadata_mismatch",
        "metadata_mismatch": "route.metadata_mismatch",
        "missing_metadata": "route.metadata_missing",
        "opaque_metadata": "route.opaque",
        "high_evasion": "identity.evasion_rate_high",
        "high_refusal": "identity.refusal_rate_high",
        "severe_baseline_drift": "baseline.score_drop",
        "downgrade_suspected": "downgrade.identity_instability",
        "downgrade_likely": "downgrade.identity_instability",
    }
    return mapping.get(key, "identity.false_claim")


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
    opaque_metadata: bool = False,
    downgrade_status: DowngradeStatus = DowngradeStatus.NONE,
    baseline_drift_severe: bool = False,
) -> tuple[int, list[str], list[ScoreFinding], bool, int]:
    score = SCORE_START
    warnings: list[str] = []
    findings: list[ScoreFinding] = []

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
            msg = f"Identity hijack detected in probe {result.probe_id}"
            warnings.append(msg)
            findings.append(
                ScoreFinding(
                    id="identity.hijack_suspected",
                    severity="critical",
                    penalty=penalty,
                    probe_id=result.probe_id,
                    reason=msg,
                )
            )
            continue

        if result.detection and result.detection.classification == AFFIRMED:
            key = _penalty_key_for_category(result.probe_category)
            penalty = PENALTIES[key]
            score -= penalty
            false_identity_count += 1
            msg = f"False identity in probe {result.probe_id}"
            warnings.append(msg)
            findings.append(
                ScoreFinding(
                    id=_finding_id_for_penalty_key(key),
                    severity="high",
                    penalty=penalty,
                    probe_id=result.probe_id,
                    reason=msg,
                    evidence=result.response_text[:200] if result.response_text else None,
                )
            )

    penalty_specs: list[tuple[str, bool, str, str]] = [
        ("route_mismatch", route_mismatch, "Route/provider metadata mismatch detected", "high"),
        ("metadata_mismatch", metadata_mismatch, "Metadata mismatch detected", "high"),
        (
            "missing_metadata",
            missing_metadata,
            "Expected metadata was not available",
            "medium",
        ),
        (
            "opaque_metadata",
            opaque_metadata,
            "Route metadata is opaque; cannot verify routing integrity",
            "warning",
        ),
    ]
    for key, active, msg, severity in penalty_specs:
        if not active:
            continue
        penalty = PENALTIES[key]
        score -= penalty
        warnings.append(msg)
        findings.append(
            ScoreFinding(
                id=_finding_id_for_penalty_key(key),
                severity=severity,
                penalty=penalty,
                reason=msg,
            )
        )

    metrics = compute_metrics(results)
    if metrics.evasion_rate > 0.5:
        penalty = PENALTIES["high_evasion"]
        score -= penalty
        msg = "High evasion rate observed"
        warnings.append(msg)
        findings.append(
            ScoreFinding(
                id="identity.evasion_rate_high",
                severity="medium",
                penalty=penalty,
                reason=msg,
                confidence=metrics.evasion_rate,
            )
        )

    if metrics.refusal_rate > 0.5:
        penalty = PENALTIES["high_refusal"]
        score -= penalty
        msg = "High refusal rate observed"
        warnings.append(msg)
        findings.append(
            ScoreFinding(
                id="identity.refusal_rate_high",
                severity="medium",
                penalty=penalty,
                reason=msg,
                confidence=metrics.refusal_rate,
            )
        )

    if baseline_drift_severe:
        penalty = PENALTIES["severe_baseline_drift"]
        score -= penalty
        msg = "Severe baseline drift detected"
        warnings.append(msg)
        findings.append(
            ScoreFinding(
                id="baseline.score_drop",
                severity="high",
                penalty=penalty,
                reason=msg,
            )
        )

    if downgrade_status == DowngradeStatus.SUSPECTED:
        penalty = PENALTIES["downgrade_suspected"]
        score -= penalty
        msg = "Downgrade suspected based on heuristic signals"
        warnings.append(msg)
        findings.append(
            ScoreFinding(
                id="downgrade.identity_instability",
                severity="medium",
                penalty=penalty,
                reason=msg,
            )
        )
    elif downgrade_status == DowngradeStatus.LIKELY:
        penalty = PENALTIES["downgrade_likely"]
        score -= penalty
        msg = "Downgrade likely based on multiple signals"
        warnings.append(msg)
        findings.append(
            ScoreFinding(
                id="downgrade.identity_instability",
                severity="high",
                penalty=penalty,
                reason=msg,
            )
        )

    score = max(0, min(100, score))
    return score, warnings, findings, hijack_confirmed, false_identity_count


def determine_status(
    score: int,
    *,
    hijack_confirmed: bool,
    route_mismatch: bool,
    false_identity_count: int,
    error_count: int,
    total_probes: int,
    skipped_count: int,
    downgrade_status: DowngradeStatus,
    dry_run: bool = False,
    all_skipped: bool = False,
) -> VerificationStatus:
    if dry_run or all_skipped:
        return VerificationStatus.INCONCLUSIVE

    if error_count > 0 and error_count >= total_probes:
        return VerificationStatus.ERROR

    if total_probes == 0:
        return VerificationStatus.INCONCLUSIVE

    if skipped_count == total_probes:
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


def determine_risk_level(
    status: VerificationStatus,
    score: int,  # noqa: ARG001
    *,
    dry_run: bool = False,
) -> RiskLevel:
    if dry_run:
        return RiskLevel.LOW_INFO
    if status in (VerificationStatus.HIJACK, VerificationStatus.ROUTE_MISMATCH):
        return RiskLevel.CRITICAL
    if status == VerificationStatus.FAIL:
        return RiskLevel.HIGH
    if status == VerificationStatus.DOWNGRADE_SUSPECTED:
        return RiskLevel.HIGH
    if status == VerificationStatus.WARN:
        return RiskLevel.MEDIUM
    if status == VerificationStatus.INCONCLUSIVE:
        return RiskLevel.LOW_INFO
    if status == VerificationStatus.PASS:
        return RiskLevel.LOW
    return RiskLevel.MEDIUM


def score_report(report: VerificationReport) -> VerificationReport:
    all_skipped = (
        report.metrics.total_probes > 0
        and report.metrics.skipped_probes == report.metrics.total_probes
    )

    if report.dry_run:
        finding = ScoreFinding(
            id="dry_run.no_verification",
            severity="info",
            penalty=0,
            reason="Dry run mode: no provider calls were made and no verification was performed",
        )
        report.confidence_score = 0
        report.verification_status = VerificationStatus.INCONCLUSIVE
        report.risk_level = RiskLevel.LOW_INFO
        report.score_findings = [finding]
        report.warnings.append(finding.reason)
        return report

    if all_skipped:
        finding = ScoreFinding(
            id="report.all_skipped",
            severity="info",
            penalty=0,
            reason="All probes were skipped; verification is inconclusive",
        )
        report.confidence_score = 0
        report.verification_status = VerificationStatus.INCONCLUSIVE
        report.risk_level = RiskLevel.LOW_INFO
        report.score_findings = [finding]
        report.warnings.append(finding.reason)
        return report

    route = report.route_metadata
    route_mismatch = bool(route and route.metadata_mismatch)
    missing_metadata = bool(route and not route.metadata_available)
    opaque_metadata = bool(
        route and (route.metadata_opaque or route.match_type == RouteMatchType.METADATA_OPAQUE)
    )
    metadata_mismatch = route_mismatch

    score, warnings, findings, hijack, false_count = compute_score(
        report.probe_results,
        route_mismatch=route_mismatch,
        metadata_mismatch=metadata_mismatch,
        missing_metadata=missing_metadata,
        opaque_metadata=opaque_metadata,
        downgrade_status=report.downgrade_status,
    )

    status = determine_status(
        score,
        hijack_confirmed=hijack,
        route_mismatch=route_mismatch,
        false_identity_count=false_count,
        error_count=report.metrics.error_probes,
        total_probes=report.metrics.total_probes,
        skipped_count=report.metrics.skipped_probes,
        downgrade_status=report.downgrade_status,
        dry_run=report.dry_run,
        all_skipped=all_skipped,
    )

    report.confidence_score = score
    report.verification_status = status
    report.risk_level = determine_risk_level(status, score, dry_run=report.dry_run)
    report.score_findings = findings
    report.warnings.extend(warnings)
    return report
