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


def render_sarif_report(report: VerificationReport) -> str:
    results = []
    for probe_result in report.probe_results:
        if probe_result.outcome.value in ("PASS", "SKIP"):
            continue
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
                },
            }
        )

    if report.verification_status != VerificationStatus.PASS:
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
            }
        )

    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "model-identity-verifier",
                        "version": report.tool_version,
                        "informationUri": "https://github.com/model-identity-verifier/model-identity-verifier",
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
