"""Markdown report output."""

from __future__ import annotations

from pathlib import Path

from model_identity_verifier.models.schemas import VerificationReport


def _format_score(report: VerificationReport) -> str:
    if report.dry_run:
        return "N/A"
    if (
        report.metrics.total_probes > 0
        and report.metrics.skipped_probes == report.metrics.total_probes
    ):
        return "N/A"
    return f"{report.confidence_score}/100"


def render_markdown_report(report: VerificationReport) -> str:
    lines = [
        "# Model Identity Verification Report",
        "",
        "## Summary",
        "",
        f"**Session:** {report.session_id}",
        f"**Timestamp:** {report.timestamp}",
        f"**Provider:** {report.provider}",
        f"**Requested model:** {report.requested_model}",
        f"**Expected identity:** {report.expected_identity}",
        f"**Status:** {report.verification_status.value}",
        f"**Score:** {_format_score(report)}",
        f"**Risk level:** {report.risk_level.value}",
        f"**Dry run:** {'yes' if report.dry_run else 'no'}",
        "",
        f"- Schema version: {report.schema_version}",
        f"- Detector version: {report.detector_version}",
        f"- Scoring version: {report.scoring_version}",
        f"- Probe set version: {report.probe_set_version}",
        "",
        "## Metrics",
        "",
        f"- Total probes: {report.metrics.total_probes}",
        f"- Passed: {report.metrics.passed_probes}",
        f"- Failed: {report.metrics.failed_probes}",
        f"- Identity match rate: {report.metrics.identity_match_rate:.2%}",
        f"- False identity rate: {report.metrics.false_identity_rate:.2%}",
        "",
    ]

    if report.dry_run:
        lines.extend(
            [
                "> This is a dry-run report. No provider calls were made and no model "
                "identity behavior was verified.",
                "",
            ]
        )

    lines.extend(["## Scoring Findings", ""])
    if report.score_findings:
        for finding in report.score_findings:
            penalty = f" (penalty: {finding.penalty})" if finding.penalty else ""
            lines.append(f"- **{finding.id}** [{finding.severity}]{penalty}: {finding.reason}")
    else:
        lines.append("- No scoring findings recorded.")

    lines.extend(
        [
            "",
            "## Probe Results",
            "",
            "| Probe ID | Category | Outcome | Detection |",
            "| --- | --- | --- | --- |",
        ]
    )

    for result in report.probe_results:
        detection = result.detection.classification.value if result.detection else "-"
        lines.append(
            f"| {result.probe_id} | {result.probe_category.value} | "
            f"{result.outcome.value} | {detection} |"
        )

    lines.extend(["", "## Route Metadata", ""])
    if report.route_metadata:
        route = report.route_metadata
        lines.extend(
            [
                f"- Metadata available: {route.metadata_available}",
                f"- Metadata opaque: {route.metadata_opaque}",
                f"- Match type: {route.match_type.value if route.match_type else 'unknown'}",
                f"- Returned model: {route.returned_model or 'unknown'}",
                f"- Upstream provider: {route.upstream_provider or 'unknown'}",
            ]
        )
        if route.mismatch_details:
            lines.append("- Details:")
            lines.extend(f"  - {detail}" for detail in route.mismatch_details)
    else:
        lines.append("- No route metadata captured.")

    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {w}" for w in report.warnings)

    if report.errors:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {e}" for e in report.errors)

    lines.extend(
        [
            "",
            "## Limitations",
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
