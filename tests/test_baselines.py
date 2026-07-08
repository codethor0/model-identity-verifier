"""Tests for baseline and report comparison."""

from pathlib import Path

from model_identity_verifier.baselines.manager import (
    baseline_from_report,
    baseline_schema_warnings,
    check_drift,
    compare_reports,
    save_baseline,
)
from model_identity_verifier.models.enums import (
    ProbeCategory,
    ProbeOutcome,
    RiskLevel,
    RouteMatchType,
    VerificationStatus,
)
from model_identity_verifier.models.schemas import (
    DETECTOR_VERSION,
    PROBE_SET_VERSION,
    SCHEMA_VERSION,
    SCORING_VERSION,
    ProbeResult,
    ReportMetrics,
    RouteMetadata,
    ScoreFinding,
    VerificationReport,
)


def _report(
    *,
    session: str,
    status: VerificationStatus = VerificationStatus.PASS,
    score: int = 100,
    route_model: str = "mock-model",
    findings: list[ScoreFinding] | None = None,
) -> VerificationReport:
    return VerificationReport(
        tool_version="0.1.2",
        session_id=session,
        timestamp="2026-01-01T00:00:00+00:00",
        provider="mock",
        requested_model="mock-model",
        expected_identity="claude",
        verification_status=status,
        confidence_score=score,
        risk_level=RiskLevel.LOW,
        route_metadata=RouteMetadata(
            returned_model=route_model,
            metadata_available=True,
            match_type=RouteMatchType.EXACT_MATCH,
        ),
        metrics=ReportMetrics(total_probes=1, passed_probes=1, identity_match_rate=1.0),
        probe_results=[
            ProbeResult(
                probe_id="base-identity-001",
                probe_category=ProbeCategory.BASE,
                outcome=ProbeOutcome.PASS,
            )
        ],
        score_findings=findings or [],
    )


def test_baseline_includes_schema_versions() -> None:
    report = _report(session="baseline-schema")
    baseline = baseline_from_report(report)
    assert baseline.schema_version == SCHEMA_VERSION
    assert baseline.probe_set_version == PROBE_SET_VERSION
    assert baseline.detector_version == DETECTOR_VERSION
    assert baseline.scoring_version == SCORING_VERSION


def test_baseline_schema_warnings_on_mismatch() -> None:
    report = _report(session="baseline-warn")
    baseline = baseline_from_report(report)
    baseline.schema_version = "0.0.0"
    warnings = baseline_schema_warnings(baseline)
    assert any("schema version" in w.lower() for w in warnings)


def test_check_drift_reports_schema_warnings(tmp_path: Path) -> None:
    report = _report(session="drift-schema")
    baseline = baseline_from_report(report, baseline_id="b1")
    baseline.scoring_version = "0.0.0"
    path = tmp_path / "baseline.json"
    save_baseline(baseline, path)
    drift = check_drift(baseline, report)
    assert any("scoring version" in w.lower() for w in drift.warnings)


def test_compare_reports_route_and_findings_diff() -> None:
    report_a = _report(
        session="a",
        route_model="gpt-4o",
        findings=[ScoreFinding(id="identity.false_claim", severity="high", reason="a")],
    )
    report_b = _report(
        session="b",
        route_model="other-model",
        findings=[
            ScoreFinding(id="route.opaque", severity="warning", reason="b"),
            ScoreFinding(id="identity.false_claim", severity="high", reason="a"),
        ],
    )
    comparison = compare_reports(report_a, report_b)
    assert comparison["route_metadata_changed"] is True
    assert comparison["score_findings_added"] == ["route.opaque"]
    assert comparison["score_findings_removed"] == []
    assert comparison["identity_match_rate_delta"] == 0.0


def test_compare_reports_score_findings_removed() -> None:
    report_a = _report(
        session="a",
        findings=[
            ScoreFinding(id="route.metadata_missing", severity="medium", reason="missing"),
            ScoreFinding(id="identity.false_claim", severity="high", reason="false"),
        ],
    )
    report_b = _report(session="b", findings=[])
    comparison = compare_reports(report_a, report_b)
    assert "route.metadata_missing" in comparison["score_findings_removed"]
    assert "identity.false_claim" in comparison["score_findings_removed"]
