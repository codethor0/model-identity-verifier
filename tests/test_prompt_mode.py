"""Tests for manual prompt-mode workflow."""

from pathlib import Path

import pytest

from model_identity_verifier.cli import EXIT_FAIL, EXIT_SUCCESS, EXIT_WARN, main
from model_identity_verifier.models.enums import VerificationStatus
from model_identity_verifier.prompts.assessor import run_manual_assessment, split_responses
from model_identity_verifier.prompts.packs import (
    RESPONSE_DELIMITER,
    format_prompt_pack,
    get_prompt_pack,
)

FIXTURES = Path(__file__).parent / "fixtures" / "manual"


def test_split_responses_single_block() -> None:
    assert split_responses("hello") == ["hello"]


def test_split_responses_delimiter() -> None:
    text = f"first{RESPONSE_DELIMITER}second"
    assert split_responses(text) == ["first", "second"]


def test_get_prompt_pack_quick() -> None:
    probes = get_prompt_pack("chatgpt", "quick")
    assert len(probes) == 6
    assert probes[0].id == "base-identity-001"


def test_get_prompt_pack_deep_includes_boundary() -> None:
    probes = get_prompt_pack("claude", "deep")
    assert any(p.id == "manual-boundary-001" for p in probes)


def test_format_prompt_pack_json() -> None:
    content = format_prompt_pack("chatgpt", "quick", "json")
    assert '"expected_identity": "chatgpt"' in content
    assert "Manual prompt mode does not call" in content


def test_format_prompt_pack_markdown() -> None:
    content = format_prompt_pack("claude", "quick", "markdown")
    assert "# Model Identity Verifier" in content
    assert "claude" in content.lower()


def test_manual_assessment_consistent_chatgpt() -> None:
    text = (FIXTURES / "chatgpt_consistent.txt").read_text(encoding="utf-8")
    report = run_manual_assessment("chatgpt", text, mode="quick")
    assert report.manual_mode is True
    assert report.provider == "manual"
    assert report.dry_run is False
    assert report.schema_version
    assert report.score_findings is not None
    assert report.verification_status in (
        VerificationStatus.PASS,
        VerificationStatus.WARN,
        VerificationStatus.INCONCLUSIVE,
    )


def test_manual_assessment_wrong_identity_fails() -> None:
    text = (FIXTURES / "chatgpt_says_claude.txt").read_text(encoding="utf-8")
    report = run_manual_assessment("chatgpt", text, mode="quick")
    assert report.verification_status in (
        VerificationStatus.FAIL,
        VerificationStatus.WARN,
        VerificationStatus.HIJACK,
    )


def test_manual_assessment_hijack_fixture() -> None:
    text = (FIXTURES / "hijack_accepted.txt").read_text(encoding="utf-8")
    report = run_manual_assessment("claude", text, mode="quick")
    assert report.verification_status in (
        VerificationStatus.FAIL,
        VerificationStatus.HIJACK,
        VerificationStatus.WARN,
    )


def test_manual_assessment_warnings_include_limitation() -> None:
    text = (FIXTURES / "chatgpt_consistent.txt").read_text(encoding="utf-8")
    report = run_manual_assessment("chatgpt", text, mode="quick")
    joined = " ".join(report.warnings).lower()
    assert "manual" in joined
    assert "route metadata" in joined


def test_cli_prompt_create(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["prompt", "create", "--expected-identity", "chatgpt", "--mode", "quick"])
    assert exc.value.code == EXIT_SUCCESS
    assert "Manual prompt mode" in capsys.readouterr().out


def test_cli_prompt_assess_fixture(tmp_path: Path) -> None:
    out = tmp_path / "manual.json"
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "prompt",
                "assess",
                "--expected-identity",
                "chatgpt",
                "--response-file",
                str(FIXTURES / "chatgpt_consistent.txt"),
                "--format",
                "json",
                "-o",
                str(out),
            ]
        )
    assert exc.value.code in (EXIT_SUCCESS, EXIT_WARN, EXIT_FAIL)
    assert out.exists()
    data = out.read_text(encoding="utf-8")
    assert '"manual_mode": true' in data
    assert '"provider": "manual"' in data
