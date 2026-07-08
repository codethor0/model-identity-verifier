"""Tests for reports."""

import json

from model_identity_verifier.models.enums import (
    ProbeCategory,
    ProbeOutcome,
    RiskLevel,
    VerificationStatus,
)
from model_identity_verifier.models.schemas import ProbeResult, ReportMetrics, VerificationReport
from model_identity_verifier.reports.json_report import render_json_report
from model_identity_verifier.reports.markdown_report import render_markdown_report
from model_identity_verifier.reports.sarif_report import render_sarif_report


def _sample_report(status: VerificationStatus = VerificationStatus.PASS) -> VerificationReport:
    return VerificationReport(
        tool_version="0.1.0",
        session_id="test-session",
        timestamp="2026-01-01T00:00:00+00:00",
        provider="mock",
        requested_model="mock-model",
        expected_identity="claude",
        verification_status=status,
        confidence_score=85,
        risk_level=RiskLevel.LOW,
        metrics=ReportMetrics(total_probes=1, passed_probes=1),
        probe_results=[
            ProbeResult(
                probe_id="base-identity-001",
                probe_category=ProbeCategory.BASE,
                outcome=ProbeOutcome.PASS,
            )
        ],
        report_hash="abc123",
    )


def test_json_report_valid() -> None:
    report = _sample_report()
    output = render_json_report(report)
    data = json.loads(output)
    assert data["verification_status"] == "PASS"
    assert data["tool_version"] == "0.1.0"


def test_markdown_report_renders() -> None:
    report = _sample_report(VerificationStatus.WARN)
    output = render_markdown_report(report)
    assert "# Model Identity Verification Report" in output
    assert "WARN" in output
    assert "not attestation" in output


def test_sarif_report_valid() -> None:
    report = _sample_report(VerificationStatus.FAIL)
    report.confidence_score = 40
    output = render_sarif_report(report)
    data = json.loads(output)
    assert data["version"] == "2.1.0"
    assert len(data["runs"]) == 1
