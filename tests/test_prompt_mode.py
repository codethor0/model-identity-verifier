"""Tests for manual prompt-mode workflow."""

import json
from pathlib import Path

import pytest

from model_identity_verifier.cli import EXIT_ERROR, EXIT_FAIL, EXIT_SUCCESS, EXIT_WARN, main
from model_identity_verifier.models.enums import VerificationStatus
from model_identity_verifier.prompts.assessor import run_manual_assessment, split_responses
from model_identity_verifier.prompts.packs import (
    RESPONSE_DELIMITER,
    format_prompt_pack,
    format_response_template,
    get_prompt_pack,
)

FIXTURES = Path(__file__).parent / "fixtures" / "manual"

FREEFORM_WARNING = (
    "Manual free-form assessment: no provider metadata or prompt-pack alignment was verified."
)


def test_split_responses_single_block() -> None:
    assert split_responses("hello") == ["hello"]


def test_split_responses_delimiter() -> None:
    text = f"first{RESPONSE_DELIMITER}second"
    assert split_responses(text) == ["first", "second"]


def test_get_prompt_pack_quick() -> None:
    probes = get_prompt_pack("chatgpt", "quick")
    assert len(probes) == 10
    assert probes[0].id == "base-identity-001"


def test_get_prompt_pack_deep_includes_boundary() -> None:
    probes = get_prompt_pack("claude", "deep")
    assert any(p.id == "manual-boundary-001" for p in probes)


def test_format_prompt_pack_json() -> None:
    content = format_prompt_pack("chatgpt", "quick", "json")
    assert '"expected_identity": "chatgpt"' in content
    assert "Manual prompt mode does not call" in content
    json.loads(content)


def test_format_prompt_pack_markdown_includes_limitation() -> None:
    content = format_prompt_pack("claude", "quick", "markdown")
    assert "# Model Identity Verifier" in content
    assert "cannot verify provider route metadata" in content.lower()
    assert "Response collection template" in content


def test_response_template_slot_count_matches_prompts() -> None:
    probes = get_prompt_pack("chatgpt", "quick")
    template = format_response_template("chatgpt", "quick")
    assert template.count(RESPONSE_DELIMITER) == len(probes)


def test_response_template_includes_delimiter_instructions() -> None:
    template = format_response_template("chatgpt", "quick")
    assert "Paste response for prompt 1" in template
    assert "--pack-mode quick" in template


def test_freeform_assessment_consistent_chatgpt() -> None:
    text = (FIXTURES / "chatgpt_consistent.txt").read_text(encoding="utf-8")
    report = run_manual_assessment("chatgpt", text)
    assert report.manual_mode is True
    assert report.provider == "manual"
    assert report.verification_status in (
        VerificationStatus.PASS,
        VerificationStatus.WARN,
        VerificationStatus.INCONCLUSIVE,
    )
    finding_ids = [f.id for f in report.score_findings]
    assert "manual.freeform_assessment" in finding_ids
    assert FREEFORM_WARNING in " ".join(report.warnings)


def test_freeform_no_quote_boundary_false_positive() -> None:
    text = (FIXTURES / "chatgpt_consistent.txt").read_text(encoding="utf-8")
    report = run_manual_assessment("chatgpt", text)
    assert report.verification_status != VerificationStatus.FAIL
    probe_ids = [r.probe_id for r in report.probe_results]
    assert "adv-quote-001" not in probe_ids
    assert "adv-negation-001" not in probe_ids


def test_freeform_wrong_identity_fails() -> None:
    text = (FIXTURES / "chatgpt_says_claude.txt").read_text(encoding="utf-8")
    report = run_manual_assessment("chatgpt", text)
    assert report.verification_status in (
        VerificationStatus.FAIL,
        VerificationStatus.WARN,
        VerificationStatus.HIJACK,
    )


def test_pack_mode_matching_responses() -> None:
    text = (FIXTURES / "chatgpt_pack_quick.txt").read_text(encoding="utf-8")
    report = run_manual_assessment("chatgpt", text, pack_mode="quick")
    finding_ids = [f.id for f in report.score_findings]
    assert "manual.prompt_pack_assessment" in finding_ids
    assert "manual.response_count_mismatch" not in finding_ids
    assert len(report.probe_results) == len(get_prompt_pack("chatgpt", "quick"))


def test_pack_mode_single_response_mismatch() -> None:
    text = (FIXTURES / "chatgpt_consistent.txt").read_text(encoding="utf-8")
    report = run_manual_assessment("chatgpt", text, pack_mode="quick")
    assert report.verification_status == VerificationStatus.INCONCLUSIVE
    finding_ids = [f.id for f in report.score_findings]
    assert "manual.response_count_mismatch" in finding_ids
    assert any("expected 10" in e.lower() for e in report.errors)


def test_manual_route_metadata_opaque() -> None:
    report = run_manual_assessment("chatgpt", "I am ChatGPT.")
    assert report.route_metadata is not None
    assert report.route_metadata.metadata_available is False
    assert report.route_metadata.metadata_opaque is True
    assert report.route_metadata.metadata_mismatch is False


def test_cli_prompt_create(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["prompt", "create", "--expected-identity", "chatgpt", "--mode", "quick"])
    assert exc.value.code == EXIT_SUCCESS
    assert "Manual prompt mode" in capsys.readouterr().out


def test_cli_prompt_template(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["prompt", "template", "--expected-identity", "chatgpt", "--mode", "quick"])
    assert exc.value.code == EXIT_SUCCESS
    assert RESPONSE_DELIMITER in capsys.readouterr().out


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
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["manual_mode"] is True
    assert data["provider"] == "manual"


def test_cli_prompt_assess_stdin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import io
    import sys

    out = tmp_path / "stdin.json"
    monkeypatch.setattr(sys, "stdin", io.StringIO("I am ChatGPT, developed by OpenAI.\n"))
    with pytest.raises(SystemExit):
        main(
            [
                "prompt",
                "assess",
                "--expected-identity",
                "chatgpt",
                "--stdin",
                "--format",
                "json",
                "-o",
                str(out),
            ]
        )
    assert out.exists()


def test_cli_prompt_assess_pack_mismatch_exit(tmp_path: Path) -> None:
    out = tmp_path / "pack.json"
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "prompt",
                "assess",
                "--expected-identity",
                "chatgpt",
                "--pack-mode",
                "quick",
                "--response-file",
                str(FIXTURES / "chatgpt_consistent.txt"),
                "--format",
                "json",
                "-o",
                str(out),
            ]
        )
    assert exc.value.code in (EXIT_WARN, EXIT_ERROR)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert any(f["id"] == "manual.response_count_mismatch" for f in data["score_findings"])
