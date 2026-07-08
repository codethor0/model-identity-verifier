"""Tests for CLI."""

from pathlib import Path

import pytest

from model_identity_verifier.cli import EXIT_ERROR, EXIT_SUCCESS, main


def test_cli_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["version"])
    assert exc.value.code == EXIT_SUCCESS


def test_cli_self_test(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["self-test"])
    assert exc.value.code == EXIT_SUCCESS


def test_cli_verify_dry_run(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["verify", "--dry-run", "--provider", "mock"])
    assert exc.value.code in (EXIT_SUCCESS, 1)


def test_cli_probes_list(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["probes", "list"])
    assert exc.value.code == EXIT_SUCCESS


def test_cli_providers_list(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["providers", "list"])
    assert exc.value.code == EXIT_SUCCESS


def test_missing_api_key_clean_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["verify", "--provider", "openai", "--model", "gpt-4o"])
    assert exc.value.code == EXIT_ERROR
    captured = capsys.readouterr()
    assert "API key" in captured.err


def test_reports_compare_with_fixtures() -> None:
    fixture_dir = Path(__file__).parent / "fixtures"
    report_a = fixture_dir / "report_pass.json"
    report_b = fixture_dir / "report_warn.json"
    if not report_a.exists():
        pytest.skip("fixtures not yet created")
    with pytest.raises(SystemExit) as exc:
        main(["reports", "compare", str(report_a), str(report_b)])
    assert exc.value.code == EXIT_SUCCESS


def test_baseline_create_and_check(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "report_pass.json"
    if not fixture.exists():
        pytest.skip("fixtures not yet created")

    baseline_out = tmp_path / "baseline.json"
    with pytest.raises(SystemExit):
        main(
            [
                "baseline",
                "create",
                "--report",
                str(fixture),
                "--output",
                str(baseline_out),
            ]
        )

    report_out = tmp_path / "report.json"
    report_out.write_text(fixture.read_text())

    with pytest.raises(SystemExit) as exc:
        main(
            [
                "baseline",
                "check",
                "--baseline",
                str(baseline_out),
                "--report",
                str(report_out),
            ]
        )
    assert exc.value.code in (EXIT_SUCCESS, 1)
