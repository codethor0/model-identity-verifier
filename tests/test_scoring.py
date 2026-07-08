"""Tests for scoring engine."""

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
    IdentityDetection,
    ProbeResult,
    ReportMetrics,
    RouteMetadata,
    VerificationReport,
)
from model_identity_verifier.scoring.engine import compute_score, determine_status, score_report


def _fail_result(probe_id: str, category: ProbeCategory) -> ProbeResult:
    return ProbeResult(
        probe_id=probe_id,
        probe_category=category,
        outcome=ProbeOutcome.FAIL,
        detection=IdentityDetection(
            classification=IdentityClassification.AFFIRMED_SELF_CLAIM,
            detected_identities=["deepseek"],
        ),
    )


def test_scoring_pass() -> None:
    results = [
        ProbeResult(
            probe_id="t1",
            probe_category=ProbeCategory.BASE,
            outcome=ProbeOutcome.PASS,
        )
    ]
    score, _, findings, hijack, false_count = compute_score(results)
    assert score == 100
    assert not findings
    status = determine_status(
        score,
        hijack_confirmed=hijack,
        route_mismatch=False,
        false_identity_count=false_count,
        error_count=0,
        total_probes=1,
        skipped_count=0,
        downgrade_status=DowngradeStatus.NONE,
    )
    assert status == VerificationStatus.PASS


def test_scoring_fail_on_repeated_false_identity() -> None:
    results = [
        _fail_result("t1", ProbeCategory.BASE),
        _fail_result("t2", ProbeCategory.MULTILINGUAL),
    ]
    score, warnings, findings, hijack, false_count = compute_score(results)
    assert score < 60
    assert false_count >= 2
    assert findings
    assert any(f.id == "identity.false_claim" for f in findings)
    status = determine_status(
        score,
        hijack_confirmed=hijack,
        route_mismatch=False,
        false_identity_count=false_count,
        error_count=0,
        total_probes=2,
        skipped_count=0,
        downgrade_status=DowngradeStatus.NONE,
    )
    assert status == VerificationStatus.FAIL
    assert warnings


def test_dry_run_finding() -> None:
    report = VerificationReport(
        tool_version="0.1.1",
        session_id="s",
        timestamp="t",
        provider="mock",
        requested_model="m",
        expected_identity="claude",
        verification_status=VerificationStatus.INCONCLUSIVE,
        confidence_score=0,
        risk_level=RiskLevel.LOW_INFO,
        metrics=ReportMetrics(total_probes=2, skipped_probes=2),
        probe_results=[],
        dry_run=True,
    )
    scored = score_report(report)
    assert scored.verification_status == VerificationStatus.INCONCLUSIVE
    assert scored.confidence_score == 0
    assert any(f.id == "dry_run.no_verification" for f in scored.score_findings)


def test_route_metadata_missing_finding() -> None:
    report = VerificationReport(
        tool_version="0.1.1",
        session_id="s",
        timestamp="t",
        provider="mock",
        requested_model="m",
        expected_identity="claude",
        verification_status=VerificationStatus.PASS,
        confidence_score=100,
        risk_level=RiskLevel.LOW,
        route_metadata=RouteMetadata(metadata_available=False),
        metrics=ReportMetrics(total_probes=1, passed_probes=1),
        probe_results=[
            ProbeResult(
                probe_id="t1",
                probe_category=ProbeCategory.BASE,
                outcome=ProbeOutcome.PASS,
            )
        ],
    )
    scored = score_report(report)
    assert any(f.id == "route.metadata_missing" for f in scored.score_findings)


def test_route_metadata_mismatch_finding() -> None:
    report = VerificationReport(
        tool_version="0.1.1",
        session_id="s",
        timestamp="t",
        provider="mock",
        requested_model="gpt-4o",
        expected_identity="chatgpt",
        verification_status=VerificationStatus.PASS,
        confidence_score=100,
        risk_level=RiskLevel.LOW,
        route_metadata=RouteMetadata(
            metadata_available=True,
            metadata_mismatch=True,
            returned_model="other-model",
        ),
        metrics=ReportMetrics(total_probes=1, passed_probes=1),
        probe_results=[
            ProbeResult(
                probe_id="t1",
                probe_category=ProbeCategory.BASE,
                outcome=ProbeOutcome.PASS,
            )
        ],
    )
    scored = score_report(report)
    assert any(f.id == "route.metadata_mismatch" for f in scored.score_findings)


def test_route_metadata_opaque_finding() -> None:
    report = VerificationReport(
        tool_version="0.1.2",
        session_id="s",
        timestamp="t",
        provider="mock",
        requested_model="gpt-4o",
        expected_identity="chatgpt",
        verification_status=VerificationStatus.PASS,
        confidence_score=100,
        risk_level=RiskLevel.LOW,
        route_metadata=RouteMetadata(
            metadata_available=True,
            metadata_opaque=True,
            match_type=RouteMatchType.METADATA_OPAQUE,
            returned_model="gpt-4o",
        ),
        metrics=ReportMetrics(total_probes=1, passed_probes=1),
        probe_results=[
            ProbeResult(
                probe_id="t1",
                probe_category=ProbeCategory.BASE,
                outcome=ProbeOutcome.PASS,
            )
        ],
    )
    scored = score_report(report)
    opaque = [f for f in scored.score_findings if f.id == "route.opaque"]
    assert len(opaque) == 1
    assert opaque[0].severity == "warning"
    assert opaque[0].penalty == 10


def test_high_refusal_rate_finding() -> None:
    results = [
        ProbeResult(
            probe_id=f"t{i}",
            probe_category=ProbeCategory.BASE,
            outcome=ProbeOutcome.WARN,
            detection=IdentityDetection(
                classification=IdentityClassification.REFUSAL,
            ),
        )
        for i in range(3)
    ]
    score, _, findings, _, _ = compute_score(results)
    assert score < 100
    assert any(f.id == "identity.refusal_rate_high" for f in findings)


def test_high_evasion_rate_finding() -> None:
    results = [
        ProbeResult(
            probe_id=f"t{i}",
            probe_category=ProbeCategory.BASE,
            outcome=ProbeOutcome.WARN,
            detection=IdentityDetection(
                classification=IdentityClassification.NO_IDENTITY_CLAIM,
            ),
        )
        for i in range(3)
    ]
    _score, _, findings, _, _ = compute_score(results)
    assert any(f.id == "identity.evasion_rate_high" for f in findings)


def test_downgrade_suspected_finding() -> None:
    report = VerificationReport(
        tool_version="0.1.1",
        session_id="s",
        timestamp="t",
        provider="mock",
        requested_model="m",
        expected_identity="claude",
        verification_status=VerificationStatus.PASS,
        confidence_score=100,
        risk_level=RiskLevel.LOW,
        downgrade_status=DowngradeStatus.SUSPECTED,
        metrics=ReportMetrics(total_probes=1, passed_probes=1),
        probe_results=[
            ProbeResult(
                probe_id="t1",
                probe_category=ProbeCategory.BASE,
                outcome=ProbeOutcome.PASS,
            )
        ],
    )
    scored = score_report(report)
    assert any(f.id == "downgrade.identity_instability" for f in scored.score_findings)
