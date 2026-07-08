"""Terminal report rendering."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from model_identity_verifier.models.schemas import VerificationReport

console = Console()


def _format_score(report: VerificationReport) -> str:
    if report.dry_run or (
        report.verification_status.value == "INCONCLUSIVE"
        and report.metrics.skipped_probes == report.metrics.total_probes
    ):
        return "N/A"
    return f"{report.confidence_score}/100"


def render_terminal_report(report: VerificationReport) -> None:
    console.print("\n[bold]Model Identity Verification Report[/bold]")
    console.print(f"Session: {report.session_id}")
    console.print(f"Provider: {report.provider} | Model: {report.requested_model}")
    console.print(f"Expected identity: {report.expected_identity}")
    console.print(f"Status: [bold]{report.verification_status.value}[/bold]")
    console.print(f"Score: {_format_score(report)} | Risk: {report.risk_level.value}")
    console.print(f"Dry run: {'yes' if report.dry_run else 'no'}")
    route_available = bool(report.route_metadata and report.route_metadata.metadata_available)
    console.print(f"Route metadata available: {'yes' if route_available else 'no'}")

    if report.dry_run:
        console.print(
            "[yellow]Dry run mode: no provider calls were made and no verification "
            "was performed.[/yellow]"
        )

    if report.score_findings:
        console.print("\n[bold]Main findings:[/bold]")
        for finding in report.score_findings[:8]:
            penalty = f" (-{finding.penalty})" if finding.penalty else ""
            console.print(f"  - [{finding.id}] {finding.reason}{penalty}")

    table = Table(title="Probe Results")
    table.add_column("Probe ID")
    table.add_column("Category")
    table.add_column("Outcome")
    table.add_column("Detection")

    for result in report.probe_results:
        detection = result.detection.classification.value if result.detection else "-"
        table.add_row(
            result.probe_id,
            result.probe_category.value,
            result.outcome.value,
            detection,
        )
    console.print(table)

    if report.warnings:
        console.print("\n[bold]Warnings:[/bold]")
        for warning in report.warnings:
            console.print(f"  - {warning}")

    if report.errors:
        console.print("\n[bold red]Errors:[/bold red]")
        for error in report.errors:
            console.print(f"  - {error}")

    console.print(f"\nReport hash: {report.report_hash[:16]}...")
