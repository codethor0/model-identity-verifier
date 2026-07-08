"""JSON report output."""

from __future__ import annotations

import json
from pathlib import Path

from model_identity_verifier.models.schemas import VerificationReport


def render_json_report(report: VerificationReport, indent: int = 2) -> str:
    data = report.model_dump(mode="json")
    return json.dumps(data, indent=indent, ensure_ascii=False)


def save_json_report(report: VerificationReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_json_report(report), encoding="utf-8")
