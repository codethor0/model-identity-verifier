"""Markdown report output."""

from __future__ import annotations

from pathlib import Path

from model_identity_verifier.models.schemas import VerificationReport


def render_markdown_report(report: VerificationReport) -> str:
    lines = [
        "# Model Identity Verification Report",
        "",
        f"**Session:** {report.session_id}",
        f"**Timestamp:** {report.timestamp}",
        f"**Provider:** {report.provider}",
        f"**Requested model:** {report.requested_model}",
        f"**Expected identity:** {report.expected_identity}",
        f"**Status:** {report.verification_status.value}",
        f"**Score:** {report.confidence_score}/100",
        f"**Risk level:** {report.risk_level.value}",
        "",
        "## Metrics",
        "",
        f"- Total probes: {report.metrics.total_probes}",
        f"- Passed: {report.metrics.passed_probes}",
        f"- Failed: {report.metrics.failed_probes}",
        f"- Identity match rate: {report.metrics.identity_match_rate:.2%}",
        f"- False identity rate: {report.metrics.false_identity_rate:.2%}",
        "",
        "## Probe Results",
        "",
        "| Probe ID | Category | Outcome | Detection |",
        "| --- | --- | --- | --- |",
    ]

    for result in report.probe_results:
        detection = result.detection.classification.value if result.detection else "-"
        lines.append(
            f"| {result.probe_id} | {result.probe_category.value} | "
            f"{result.outcome.value} | {detection} |"
        )

    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {w}" for w in report.warnings)

    if report.errors:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {e}" for e in report.errors)

    lines.extend(
        [
            "",
            "## Limitation",
            "",
            "Model self-identification is generated text. It is not attestation.",
            "",
            f"**Report hash:** `{report.report_hash}`",
        ]
    )

    return "\n".join(lines)


def save_markdown_report(report: VerificationReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown_report(report), encoding="utf-8")
