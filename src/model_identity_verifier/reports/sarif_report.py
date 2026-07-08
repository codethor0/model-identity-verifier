"""SARIF report output."""

from __future__ import annotations

import json
from pathlib import Path

from model_identity_verifier.models.enums import VerificationStatus
from model_identity_verifier.models.schemas import VerificationReport

_LEVEL_MAP = {
    VerificationStatus.PASS: "note",
    VerificationStatus.WARN: "warning",
    VerificationStatus.FAIL: "error",
    VerificationStatus.HIJACK: "error",
    VerificationStatus.ROUTE_MISMATCH: "error",
    VerificationStatus.DOWNGRADE_SUSPECTED: "warning",
    VerificationStatus.ERROR: "error",
    VerificationStatus.INCONCLUSIVE: "note",
}

_SEVERITY_MAP = {
    "info": "note",
    "low": "note",
    "medium": "warning",
    "high": "error",
    "critical": "error",
}


def render_sarif_report(report: VerificationReport) -> str:
    rule_ids: set[str] = set()
    results: list[dict[str, object]] = []

    for finding in report.score_findings:
        rule_ids.add(finding.id)
        results.append(
            {
                "ruleId": finding.id,
                "level": _SEVERITY_MAP.get(finding.severity, "warning"),
                "message": {"text": finding.reason},
                "properties": {
                    "penalty": finding.penalty,
                    "probe_id": finding.probe_id,
                    "provider": report.provider,
                    "requested_model": report.requested_model,
                    "expected_identity": report.expected_identity,
                },
            }
        )

    for probe_result in report.probe_results:
        if probe_result.outcome.value in ("PASS", "SKIP"):
            continue
        rule_ids.add(probe_result.probe_id)
        level = "warning" if probe_result.outcome.value == "WARN" else "error"
        results.append(
            {
                "ruleId": probe_result.probe_id,
                "level": level,
                "message": {
                    "text": (
                        f"Probe {probe_result.probe_id} outcome: {probe_result.outcome.value}"
                    ),
                },
                "properties": {
                    "category": probe_result.probe_category.value,
                    "provider": report.provider,
                    "requested_model": report.requested_model,
                    "expected_identity": report.expected_identity,
                },
            }
        )

    if report.verification_status != VerificationStatus.PASS:
        rule_ids.add("verification-status")
        results.append(
            {
                "ruleId": "verification-status",
                "level": _LEVEL_MAP.get(report.verification_status, "warning"),
                "message": {
                    "text": (
                        f"Verification status: {report.verification_status.value} "
                        f"(score: {report.confidence_score})"
                    ),
                },
                "properties": {
                    "provider": report.provider,
                    "requested_model": report.requested_model,
                    "expected_identity": report.expected_identity,
                    "dry_run": report.dry_run,
                },
            }
        )

    rules = [
        {
            "id": rule_id,
            "shortDescription": {"text": rule_id},
        }
        for rule_id in sorted(rule_ids)
    ]

    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "model-identity-verifier",
                        "version": report.tool_version,
                        "informationUri": "https://github.com/codethor0/model-identity-verifier",
                        "rules": rules,
                    },
                },
                "results": results,
            }
        ],
    }
    return json.dumps(sarif, indent=2)


def save_sarif_report(report: VerificationReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_sarif_report(report), encoding="utf-8")
