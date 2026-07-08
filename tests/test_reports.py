"""Tests for reports."""

import json

from model_identity_verifier.engine.verifier import run_verification
from model_identity_verifier.models.enums import (
    ProbeCategory,
    ProbeOutcome,
    RiskLevel,
    VerificationStatus,
)
from model_identity_verifier.models.schemas import (
    ProbeResult,
    ReportMetrics,
    ScoreFinding,
    VerificationReport,
)
from model_identity_verifier.providers.base import get_provider
from model_identity_verifier.reports.json_report import render_json_report
from model_identity_verifier.reports.markdown_report import render_markdown_report
from model_identity_verifier.reports.sarif_report import render_sarif_report
from model_identity_verifier.reports.terminal import render_terminal_report


def _sample_report(status: VerificationStatus = VerificationStatus.PASS) -> VerificationReport:
    return VerificationReport(
        tool_version="0.1.1",
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
        score_findings=[
            ScoreFinding(
                id="identity.false_claim",
                severity="high",
                penalty=25,
                reason="Example finding",
            )
        ],
        report_hash="abc123",
    )


def test_json_report_valid() -> None:
    report = _sample_report()
    output = render_json_report(report)
    data = json.loads(output)
    assert data["verification_status"] == "PASS"
    assert data["tool_version"] == "0.1.1"
    assert data["schema_version"] == "1.0"
    assert data["scoring_version"] == "1.0"
    assert data["detector_version"] == "1.0"
    assert data["probe_set_version"] == "builtin-1"
    assert data["score_findings"]


def test_markdown_report_renders() -> None:
    report = _sample_report(VerificationStatus.WARN)
    output = render_markdown_report(report)
    assert "# Model Identity Verification Report" in output
    assert "WARN" in output
    assert "Scoring Findings" in output
    assert "not attestation" in output


def test_markdown_dry_run_notice() -> None:
    provider = get_provider("mock")
    report = run_verification(provider, "mock-model", "claude", dry_run=True)
    output = render_markdown_report(report)
    assert "dry-run report" in output.lower()
    assert "N/A" in output


def test_sarif_report_valid() -> None:
    report = _sample_report(VerificationStatus.FAIL)
    report.confidence_score = 40
    output = render_sarif_report(report)
    data = json.loads(output)
    assert data["version"] == "2.1.0"
    assert len(data["runs"]) == 1
    assert data["runs"][0]["tool"]["driver"]["rules"]


def test_terminal_dry_run_not_pass(capsys) -> None:
    provider = get_provider("mock")
    report = run_verification(provider, "mock-model", "claude", dry_run=True)
    render_terminal_report(report)
    output = capsys.readouterr().out
    assert "INCONCLUSIVE" in output
    assert "PASS" not in output.split("Status:")[1].split("\n")[0]
    assert "N/A" in output
    assert "100/100" not in output
    assert "no verification was performed" in output.lower()
