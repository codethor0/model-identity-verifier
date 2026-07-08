"""Smoke report inspection and release gate evaluation."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

V013_REQUIRED_REPORTS = (
    "openai-v013-smoke.json",
    "anthropic-v013-smoke.json",
    "openrouter-v013-smoke.json",
)

ACCEPTABLE_STATUSES = frozenset({"PASS", "WARN", "INCONCLUSIVE", "DOWNGRADE_SUSPECTED"})

SECRET_PATTERNS = (
    re.compile(r"sk-proj-[a-zA-Z0-9\-]{20,}"),
    re.compile(r"sk-ant-[a-zA-Z0-9\-]{20,}"),
    re.compile(r"sk-or-[a-zA-Z0-9\-]{20,}"),
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"Bearer sk-"),
    re.compile(r"ghp_[a-zA-Z0-9]{20,}"),
    re.compile(r"github_pat_[a-zA-Z0-9_]{20,}"),
    re.compile(r"AIza[a-zA-Z0-9\-_]{20,}"),
)


@dataclass
class GateFailure:
    code: str
    report: str
    message: str


@dataclass
class GateResult:
    release: str
    report_dir: Path
    summaries: list[dict[str, Any]] = field(default_factory=list)
    failures: list[GateFailure] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures


def _truncate_errors(errors: list[str], limit: int = 2) -> list[str]:
    trimmed: list[str] = []
    for error in errors[:limit]:
        text = error.strip().replace("\n", " ")
        if len(text) > 180:
            text = f"{text[:177]}..."
        trimmed.append(text)
    if len(errors) > limit:
        trimmed.append(f"... and {len(errors) - limit} more")
    return trimmed


def _quota_hint(errors: list[str]) -> str | None:
    joined = " ".join(errors).lower()
    if "insufficient_quota" in joined or "exceeded your current quota" in joined:
        return (
            "OpenAI returned insufficient_quota (HTTP 429). "
            "This is external API Platform billing/quota, not a tool defect. "
            "ChatGPT subscription billing is separate from API Platform credits."
        )
    return None


def summarize_report(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    errors = list(data.get("errors") or [])
    route = data.get("route_metadata") or {}
    return {
        "file": path.name,
        "provider": data.get("provider"),
        "requested_model": data.get("requested_model"),
        "expected_identity": data.get("expected_identity"),
        "verification_status": data.get("verification_status"),
        "confidence_score": data.get("confidence_score"),
        "risk_level": data.get("risk_level"),
        "dry_run": data.get("dry_run"),
        "manual_mode": data.get("manual_mode"),
        "schema_version": data.get("schema_version"),
        "warnings": list(data.get("warnings") or []),
        "errors": _truncate_errors(errors),
        "error_hint": _quota_hint(errors),
        "score_findings": [item.get("id") for item in data.get("score_findings") or []],
        "route_match_type": route.get("match_type"),
        "route_metadata_available": route.get("metadata_available"),
        "route_metadata_opaque": route.get("metadata_opaque"),
        "upstream_provider": route.get("upstream_provider"),
    }


def scan_secrets(paths: list[Path]) -> list[str]:
    leaks: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                leaks.append(f"{path.name}: matched {pattern.pattern}")
                break
    return leaks


def _load_report(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        msg = f"Expected JSON object in {path}"
        raise ValueError(msg)
    return data


def evaluate_gate(
    report_dir: Path,
    *,
    release: str = "v0.1.3",
    required_reports: tuple[str, ...] = V013_REQUIRED_REPORTS,
) -> GateResult:
    result = GateResult(release=release, report_dir=report_dir)

    present_paths: list[Path] = []
    for name in required_reports:
        path = report_dir / name
        if not path.exists():
            result.failures.append(
                GateFailure(
                    code="missing_report",
                    report=name,
                    message=f"Required live smoke report missing: {name}",
                )
            )
            continue
        if path.stat().st_size == 0:
            result.failures.append(
                GateFailure(
                    code="empty_report",
                    report=name,
                    message=f"Report file is empty: {name}",
                )
            )
            continue
        present_paths.append(path)

    if present_paths:
        for leak in scan_secrets(present_paths):
            result.failures.append(
                GateFailure(
                    code="secret_leak", report="*", message=f"Possible secret leakage: {leak}"
                )
            )

    for name in required_reports:
        path = report_dir / name
        if not path.exists() or path.stat().st_size == 0:
            continue
        try:
            data = _load_report(path)
        except json.JSONDecodeError as exc:
            result.failures.append(
                GateFailure(
                    code="malformed_json",
                    report=name,
                    message=f"Malformed JSON in {name}: {exc.msg}",
                )
            )
            continue

        summary = summarize_report(path, data)
        result.summaries.append(summary)

        if data.get("dry_run") is True:
            result.failures.append(
                GateFailure(
                    code="dry_run",
                    report=name,
                    message=f"{name} has dry_run=true; live provider smoke required",
                )
            )
        if data.get("manual_mode") is True:
            result.failures.append(
                GateFailure(
                    code="manual_mode",
                    report=name,
                    message=(
                        f"{name} has manual_mode=true; browser/manual reports cannot "
                        "satisfy live provider smoke gate"
                    ),
                )
            )
        if not data.get("schema_version"):
            result.failures.append(
                GateFailure(
                    code="missing_schema_version",
                    report=name,
                    message=f"{name} missing schema_version",
                )
            )
        if data.get("score_findings") is None:
            result.failures.append(
                GateFailure(
                    code="missing_score_findings",
                    report=name,
                    message=f"{name} missing score_findings",
                )
            )

        status = data.get("verification_status")
        if status == "ERROR":
            hint = summary.get("error_hint")
            detail = hint or "verification_status=ERROR"
            result.failures.append(
                GateFailure(code="error_status", report=name, message=f"{name} blocked: {detail}")
            )
        elif status == "ROUTE_MISMATCH":
            result.failures.append(
                GateFailure(
                    code="route_mismatch",
                    report=name,
                    message=f"{name} verification_status=ROUTE_MISMATCH",
                )
            )
        elif status not in ACCEPTABLE_STATUSES:
            result.failures.append(
                GateFailure(
                    code="unexpected_status",
                    report=name,
                    message=f"{name} unexpected verification_status={status!r}",
                )
            )

    return result


def print_inspection(summaries: list[dict[str, Any]]) -> None:
    for summary in summaries:
        print(f"=== {summary['file']} ===")
        for key in (
            "provider",
            "requested_model",
            "expected_identity",
            "verification_status",
            "confidence_score",
            "risk_level",
            "dry_run",
            "manual_mode",
            "schema_version",
            "route_match_type",
            "route_metadata_available",
            "route_metadata_opaque",
            "upstream_provider",
        ):
            print(f"  {key}: {summary.get(key)}")
        print(f"  score_findings: {summary.get('score_findings')}")
        print(f"  warnings: {summary.get('warnings')}")
        print(f"  errors: {summary.get('errors')}")
        if summary.get("error_hint"):
            print(f"  error_hint: {summary.get('error_hint')}")
        print()


def print_gate_result(result: GateResult) -> None:
    print(f"==> release gate: {result.release}")
    print(f"==> report dir: {result.report_dir}")
    print("==> required smoke reports")
    for name in V013_REQUIRED_REPORTS:
        path = result.report_dir / name
        state = "present" if path.exists() and path.stat().st_size > 0 else "MISSING"
        print(f"    {name}: {state}")

    if result.summaries:
        print("==> inspect")
        print_inspection(result.summaries)

    if result.failures:
        print("==> gate failures", file=sys.stderr)
        for failure in result.failures:
            print(f"    [{failure.code}] {failure.report}: {failure.message}", file=sys.stderr)
        print(f"TAG GATE: hold — {len(result.failures)} blocker(s)", file=sys.stderr)
        return

    print("TAG GATE: proceed — smoke reports acceptable for v0.1.3 tag review")
    print('Next: git tag -s v0.1.3 -m "v0.1.3" && git push origin v0.1.3')


def inspect_paths(report_dir: Path, pattern: str) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for path in sorted(report_dir.glob(pattern)):
        if not path.is_file():
            continue
        try:
            data = _load_report(path)
        except json.JSONDecodeError:
            summaries.append({"file": path.name, "error": "malformed JSON"})
            continue
        summaries.append(summarize_report(path, data))
    return summaries


def gate_exit_code(result: GateResult) -> int:
    if any(failure.code == "missing_report" for failure in result.failures):
        return 2
    if result.failures:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect smoke reports and evaluate release gate")
    parser.add_argument(
        "--report-dir", default=".miv/reports", help="Directory containing smoke JSON"
    )
    parser.add_argument("--release", default="v0.1.3", help="Release version for gate evaluation")
    parser.add_argument(
        "--inspect-only",
        action="store_true",
        help="Print inspection summaries without gate evaluation",
    )
    parser.add_argument(
        "--glob",
        default="*v013-smoke.json",
        help="Glob for inspect-only mode",
    )
    args = parser.parse_args(argv)
    report_dir = Path(args.report_dir)

    if args.inspect_only:
        summaries = inspect_paths(report_dir, args.glob)
        if not summaries:
            print(f"No reports matched {args.glob} in {report_dir}", file=sys.stderr)
            return 2
        print_inspection(summaries)
        return 0

    result = evaluate_gate(report_dir, release=args.release)
    print_gate_result(result)
    return gate_exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
