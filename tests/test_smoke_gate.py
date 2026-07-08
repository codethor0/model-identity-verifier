"""Tests for smoke gate evaluation and report inspection."""

from __future__ import annotations

import json
from pathlib import Path

from model_identity_verifier.smoke_gate import (
    evaluate_gate,
    gate_exit_code,
    scan_secrets,
    summarize_report,
)


def _write_report(path: Path, **overrides: object) -> None:
    data = {
        "tool_version": "0.1.3",
        "session_id": "test-session",
        "timestamp": "2026-07-08T00:00:00+00:00",
        "provider": "openai",
        "requested_model": "gpt-4o-mini",
        "expected_identity": "chatgpt",
        "verification_status": "PASS",
        "confidence_score": 100,
        "risk_level": "low",
        "metrics": {
            "total_probes": 2,
            "passed_probes": 2,
            "failed_probes": 0,
            "warned_probes": 0,
            "skipped_probes": 0,
            "error_probes": 0,
            "identity_match_rate": 1.0,
            "false_identity_rate": 0.0,
            "hijack_rate": 0.0,
            "refusal_rate": 0.0,
            "evasion_rate": 0.0,
            "average_latency_ms": 1.0,
            "average_response_length": 10.0,
        },
        "warnings": [],
        "errors": [],
        "probe_results": [],
        "score_findings": [],
        "report_hash": "abc",
        "dry_run": False,
        "manual_mode": False,
        "schema_version": "1.0",
        "detector_version": "1.0",
        "scoring_version": "1.0",
        "probe_set_version": "builtin-1",
        "redaction_mode": "standard",
    }
    data.update(overrides)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_gate_passes_with_required_reports(tmp_path: Path) -> None:
    _write_report(tmp_path / "openai-v013-smoke.json", provider="openai")
    _write_report(tmp_path / "anthropic-v013-smoke.json", provider="anthropic")
    _write_report(tmp_path / "openrouter-v013-smoke.json", provider="openrouter")

    result = evaluate_gate(tmp_path)
    assert result.ok
    assert gate_exit_code(result) == 0


def test_gate_blocks_missing_report(tmp_path: Path) -> None:
    _write_report(tmp_path / "openai-v013-smoke.json")
    _write_report(tmp_path / "anthropic-v013-smoke.json")

    result = evaluate_gate(tmp_path)
    assert not result.ok
    assert any(failure.code == "missing_report" for failure in result.failures)
    assert gate_exit_code(result) == 2


def test_gate_blocks_manual_mode(tmp_path: Path) -> None:
    _write_report(tmp_path / "openai-v013-smoke.json", manual_mode=True)
    _write_report(tmp_path / "anthropic-v013-smoke.json")
    _write_report(tmp_path / "openrouter-v013-smoke.json")

    result = evaluate_gate(tmp_path)
    assert any(failure.code == "manual_mode" for failure in result.failures)


def test_gate_blocks_error_with_quota_hint(tmp_path: Path) -> None:
    _write_report(
        tmp_path / "openai-v013-smoke.json",
        verification_status="ERROR",
        errors=[
            "OpenAI API error: 429 insufficient_quota exceeded your current quota",
        ],
    )
    _write_report(tmp_path / "anthropic-v013-smoke.json", provider="anthropic")
    _write_report(tmp_path / "openrouter-v013-smoke.json", provider="openrouter")

    result = evaluate_gate(tmp_path)
    assert any(failure.code == "error_status" for failure in result.failures)
    summary = next(item for item in result.summaries if item["file"] == "openai-v013-smoke.json")
    assert summary["error_hint"] is not None
    assert "insufficient_quota" in summary["error_hint"]


def test_gate_blocks_malformed_json(tmp_path: Path) -> None:
    (tmp_path / "openai-v013-smoke.json").write_text("{not-json", encoding="utf-8")
    _write_report(tmp_path / "anthropic-v013-smoke.json", provider="anthropic")
    _write_report(tmp_path / "openrouter-v013-smoke.json", provider="openrouter")

    result = evaluate_gate(tmp_path)
    assert any(failure.code == "malformed_json" for failure in result.failures)


def test_secret_scan_detects_fake_key(tmp_path: Path) -> None:
    path = tmp_path / "openai-v013-smoke.json"
    path.write_text('{"errors":["sk-abcdefghijklmnopqrstuvwxyz123456"]}', encoding="utf-8")
    leaks = scan_secrets([path])
    assert leaks


def test_summarize_report_truncates_errors() -> None:
    summary = summarize_report(
        Path("openai-v013-smoke.json"),
        {"errors": ["x" * 300], "warnings": [], "score_findings": []},
    )
    assert len(summary["errors"][0]) <= 180
