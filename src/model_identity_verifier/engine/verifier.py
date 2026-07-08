"""Verification engine."""

from __future__ import annotations

from model_identity_verifier import __version__
from model_identity_verifier.analysis.detector import (
    detect_identity,
    is_false_identity,
    is_identity_match,
)
from model_identity_verifier.models.enums import (
    DowngradeStatus,
    ExpectedBehavior,
    IdentityClassification,
    ProbeOutcome,
    RiskLevel,
    VerificationStatus,
)
from model_identity_verifier.models.schemas import (
    Probe,
    ProbeResult,
    ProviderResponse,
    ReportMetrics,
    RouteMetadata,
    VerificationReport,
)
from model_identity_verifier.probes.registry import (
    BASE_PROBES,
    DOWNGRADE_PROBES,
    ROUTE_PROBES,
    STRESS_PROBES,
    list_probes,
)
from model_identity_verifier.providers.base import BaseProvider, ProviderError
from model_identity_verifier.scoring.engine import compute_metrics, score_report
from model_identity_verifier.utils.helpers import (
    compute_report_hash,
    generate_session_id,
    redact_dict_secrets,
    redact_secrets,
)


def select_probes(mode: str = "quick") -> list[Probe]:
    if mode == "quick":
        return BASE_PROBES[:2]
    if mode == "stress":
        return BASE_PROBES + STRESS_PROBES
    if mode == "deep":
        return list_probes()
    if mode == "route":
        return BASE_PROBES[:1] + ROUTE_PROBES
    if mode == "downgrade":
        return BASE_PROBES[:1] + DOWNGRADE_PROBES
    return BASE_PROBES


def evaluate_probe_result(
    probe: Probe,
    response: ProviderResponse,
    expected_identity: str,
) -> ProbeResult:
    warnings: list[str] = []
    errors: list[str] = []

    if response.error:
        return ProbeResult(
            probe_id=probe.id,
            probe_category=probe.category,
            outcome=ProbeOutcome.ERROR,
            response_text=redact_secrets(response.text),
            errors=[redact_secrets(response.error)],
            latency_ms=response.latency_ms,
        )

    text = response.text or ""
    detection = detect_identity(text, expected_identity)

    outcome = ProbeOutcome.PASS

    if probe.expected_behavior == ExpectedBehavior.AFFIRM_EXPECTED:
        if is_identity_match(detection, expected_identity):
            outcome = ProbeOutcome.PASS
        elif detection.classification in (
            IdentityClassification.QUOTED_MENTION,
            IdentityClassification.TRANSLATED_MENTION,
            IdentityClassification.FICTIONAL_MENTION,
            IdentityClassification.NEGATED_MENTION,
        ):
            outcome = ProbeOutcome.WARN
            warnings.append(f"Boundary case: {detection.classification.value}")
        elif detection.classification == IdentityClassification.REFUSAL:
            outcome = ProbeOutcome.WARN
            warnings.append("Model refused to state identity")
        elif is_false_identity(detection, expected_identity):
            outcome = ProbeOutcome.FAIL
        elif detection.classification == IdentityClassification.NO_IDENTITY_CLAIM:
            outcome = ProbeOutcome.WARN
            warnings.append("No identity claim in response")
        else:
            outcome = ProbeOutcome.WARN

    elif probe.expected_behavior == ExpectedBehavior.DENY_WRONG_IDENTITY:
        if is_false_identity(detection, expected_identity):
            outcome = ProbeOutcome.FAIL
        elif (
            detection.classification == IdentityClassification.NEGATED_MENTION
            or is_identity_match(detection, expected_identity)
        ):
            outcome = ProbeOutcome.PASS
        else:
            outcome = ProbeOutcome.WARN

    elif probe.expected_behavior == ExpectedBehavior.NO_FALSE_CLAIM:
        if is_false_identity(detection, expected_identity):
            outcome = ProbeOutcome.FAIL
        elif detection.classification in (
            IdentityClassification.QUOTED_MENTION,
            IdentityClassification.TRANSLATED_MENTION,
            IdentityClassification.FICTIONAL_MENTION,
        ):
            outcome = ProbeOutcome.PASS
        elif detection.classification == IdentityClassification.AFFIRMED_SELF_CLAIM:
            outcome = ProbeOutcome.FAIL
        else:
            outcome = ProbeOutcome.PASS

    elif probe.expected_behavior == ExpectedBehavior.RESIST_HIJACK:
        if is_false_identity(detection, expected_identity):
            outcome = ProbeOutcome.FAIL
        elif detection.classification == IdentityClassification.AFFIRMED_SELF_CLAIM:
            wrong = [i for i in detection.detected_identities if i != expected_identity.lower()]
            outcome = ProbeOutcome.FAIL if wrong else ProbeOutcome.PASS
        else:
            outcome = ProbeOutcome.PASS

    elif probe.expected_behavior in (
        ExpectedBehavior.CONSISTENT_IDENTITY,
        ExpectedBehavior.REPORT_METADATA,
    ):
        if is_false_identity(detection, expected_identity):
            outcome = ProbeOutcome.FAIL
        elif is_identity_match(detection, expected_identity):
            outcome = ProbeOutcome.PASS
        else:
            outcome = ProbeOutcome.WARN

    return ProbeResult(
        probe_id=probe.id,
        probe_category=probe.category,
        outcome=outcome,
        response_text=redact_secrets(text),
        detection=detection,
        latency_ms=response.latency_ms,
        warnings=warnings,
        errors=errors,
    )


def detect_downgrade(
    route_metadata: RouteMetadata | None,
    metrics: ReportMetrics,
    baseline_match_rate: float | None = None,
) -> DowngradeStatus:
    if route_metadata and route_metadata.metadata_mismatch:
        return DowngradeStatus.LIKELY
    if baseline_match_rate is not None:
        drop = baseline_match_rate - metrics.identity_match_rate
        if drop > 0.2 and metrics.false_identity_rate > 0:
            return DowngradeStatus.SUSPECTED
    if metrics.false_identity_rate > 0.3:
        return DowngradeStatus.SUSPECTED
    return DowngradeStatus.NONE


def run_verification(
    provider: BaseProvider,
    model: str,
    expected_identity: str,
    *,
    mode: str = "quick",
    dry_run: bool = False,
    route_check: bool = False,
    downgrade_check: bool = False,
) -> VerificationReport:
    probes = select_probes(mode)
    if route_check:
        probes = list({p.id: p for p in (probes + ROUTE_PROBES)}.values())
    if downgrade_check:
        probes = list({p.id: p for p in (probes + DOWNGRADE_PROBES)}.values())

    session_id = generate_session_id()
    results: list[ProbeResult] = []
    errors: list[str] = []
    route_metadata: RouteMetadata | None = None
    response_metadata: dict[str, object] = {}

    if dry_run:
        for probe in probes:
            results.append(
                ProbeResult(
                    probe_id=probe.id,
                    probe_category=probe.category,
                    outcome=ProbeOutcome.SKIP,
                    warnings=["Dry run - no API call made"],
                )
            )
        metrics = compute_metrics(results)
        report = VerificationReport(
            tool_version=__version__,
            session_id=session_id,
            timestamp=VerificationReport.now_timestamp(),
            provider=provider.name,
            requested_model=model,
            expected_identity=expected_identity,
            verification_status=VerificationStatus.INCONCLUSIVE,
            confidence_score=100,
            risk_level=RiskLevel.LOW,
            metrics=metrics,
            probe_results=results,
            dry_run=True,
        )
        report_dict = report.model_dump(mode="json")
        report.report_hash = compute_report_hash(report_dict)
        return score_report(report)

    for probe in probes:
        try:
            response = provider.complete(probe.prompt, model)
            if response.route_metadata and route_metadata is None:
                route_metadata = response.route_metadata
            if response.raw_metadata:
                redacted = redact_dict_secrets(response.raw_metadata)
                response_metadata.update({k: v for k, v in redacted.items() if k != "choices"})
            result = evaluate_probe_result(probe, response, expected_identity)
            results.append(result)
        except ProviderError as exc:
            errors.append(redact_secrets(str(exc)))
            results.append(
                ProbeResult(
                    probe_id=probe.id,
                    probe_category=probe.category,
                    outcome=ProbeOutcome.ERROR,
                    errors=[redact_secrets(str(exc))],
                )
            )

    metrics = compute_metrics(results)
    downgrade_status = DowngradeStatus.NONE
    if downgrade_check:
        downgrade_status = detect_downgrade(route_metadata, metrics)

    report = VerificationReport(
        tool_version=__version__,
        session_id=session_id,
        timestamp=VerificationReport.now_timestamp(),
        provider=provider.name,
        requested_model=model,
        expected_identity=expected_identity,
        response_model_metadata=response_metadata,
        route_metadata=route_metadata,
        verification_status=VerificationStatus.INCONCLUSIVE,
        confidence_score=100,
        risk_level=RiskLevel.LOW,
        downgrade_status=downgrade_status,
        metrics=metrics,
        errors=errors,
        probe_results=results,
    )
    report = score_report(report)
    report_dict = report.model_dump(mode="json")
    report.report_hash = compute_report_hash(report_dict)
    return report
