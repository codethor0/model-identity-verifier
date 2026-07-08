"""Command-line interface for Model Identity Verifier."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from model_identity_verifier import __version__
from model_identity_verifier.baselines.manager import (
    baseline_from_report,
    check_drift,
    compare_reports,
    load_baseline,
    save_baseline,
)
from model_identity_verifier.engine.verifier import run_verification
from model_identity_verifier.models.enums import VerificationStatus
from model_identity_verifier.models.schemas import VerificationReport
from model_identity_verifier.probes.registry import get_probe, list_probes, validate_registry
from model_identity_verifier.prompts.assessor import run_manual_assessment
from model_identity_verifier.prompts.packs import (
    format_browser_prompt,
    format_prompt_pack,
    format_response_template,
)
from model_identity_verifier.providers.base import (
    InvalidApiKeyError,
    MissingApiKeyError,
    ProviderError,
    get_provider,
    list_providers,
)
from model_identity_verifier.reports.json_report import save_json_report
from model_identity_verifier.reports.markdown_report import save_markdown_report
from model_identity_verifier.reports.sarif_report import save_sarif_report
from model_identity_verifier.reports.terminal import render_terminal_report
from model_identity_verifier.smoke_gate import (
    evaluate_gate,
    gate_exit_code,
    inspect_paths,
    print_gate_result,
    print_inspection,
)

EXIT_SUCCESS = 0
EXIT_WARN = 1
EXIT_FAIL = 2
EXIT_ERROR = 3

STATUS_EXIT_MAP = {
    VerificationStatus.PASS: EXIT_SUCCESS,
    VerificationStatus.WARN: EXIT_WARN,
    VerificationStatus.INCONCLUSIVE: EXIT_WARN,
    VerificationStatus.DOWNGRADE_SUSPECTED: EXIT_WARN,
    VerificationStatus.FAIL: EXIT_FAIL,
    VerificationStatus.HIJACK: EXIT_FAIL,
    VerificationStatus.ROUTE_MISMATCH: EXIT_FAIL,
    VerificationStatus.ERROR: EXIT_ERROR,
}


def _exit_code(status: VerificationStatus) -> int:
    return STATUS_EXIT_MAP.get(status, EXIT_ERROR)


KNOWN_EXPECTED_IDENTITIES = frozenset(
    {
        "chatgpt",
        "claude",
        "gemini",
        "deepseek",
        "llama",
        "grok",
        "mistral",
        "kimi",
        "qwen",
    }
)


def _warn_unknown_expected_identity(expected_identity: str) -> None:
    normalized = expected_identity.lower().strip()
    if normalized not in KNOWN_EXPECTED_IDENTITIES:
        print(
            f"Warning: unknown expected identity '{expected_identity}'. "
            "Known values: " + ", ".join(sorted(KNOWN_EXPECTED_IDENTITIES)),
            file=sys.stderr,
        )


def cmd_version(_args: argparse.Namespace) -> int:
    print(f"model-identity-verifier {__version__}")
    return EXIT_SUCCESS


def cmd_verify(args: argparse.Namespace) -> int:
    if args.output and args.save:
        print("Error: --output and --save cannot be used together", file=sys.stderr)
        return EXIT_ERROR

    output_path = args.output or args.save
    mode = "quick" if args.quick else args.mode
    _warn_unknown_expected_identity(args.expected_identity)

    try:
        provider_kwargs: dict[str, object] = {"api_key": args.api_key}
        if args.provider == "mock":
            provider_kwargs["expected_identity"] = args.expected_identity
        provider = get_provider(args.provider, **provider_kwargs)
        if not args.dry_run and args.provider != "mock":
            provider.require_api_key()
    except (MissingApiKeyError, ProviderError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    report = run_verification(
        provider,
        args.model,
        args.expected_identity,
        mode=mode,
        dry_run=args.dry_run,
        route_check=args.route_check,
        downgrade_check=args.downgrade_check,
    )

    if output_path:
        output_path = Path(output_path)
        suffix = output_path.suffix.lower()
        if suffix == ".json" or args.format == "json":
            save_json_report(report, output_path)
        elif suffix in (".md", ".markdown") or args.format == "markdown":
            save_markdown_report(report, output_path)
        elif suffix == ".sarif" or args.format == "sarif":
            save_sarif_report(report, output_path)
        else:
            save_json_report(report, output_path)

    if args.format == "json" and not output_path:
        print(json.dumps(report.model_dump(mode="json"), indent=2))
    elif args.format == "markdown" and not output_path:
        from model_identity_verifier.reports.markdown_report import render_markdown_report

        print(render_markdown_report(report))
    elif args.format == "sarif" and not output_path:
        from model_identity_verifier.reports.sarif_report import render_sarif_report

        print(render_sarif_report(report))
    else:
        render_terminal_report(report)

    return _exit_code(report.verification_status)


def cmd_self_test(_args: argparse.Namespace) -> int:
    errors: list[str] = []

    registry_errors = validate_registry()
    errors.extend(registry_errors)

    provider = get_provider("mock", expected_identity="claude")
    report = run_verification(
        provider,
        "mock-model",
        "claude",
        mode="quick",
        dry_run=False,
    )
    if report.metrics.total_probes == 0:
        errors.append("No probes executed in self-test")

    dry_report = run_verification(
        provider,
        "mock-model",
        "claude",
        mode="quick",
        dry_run=True,
    )
    if not dry_report.dry_run:
        errors.append("Dry run flag not set")
    if dry_report.verification_status != VerificationStatus.INCONCLUSIVE:
        errors.append("Dry run must produce INCONCLUSIVE status")
    if dry_report.confidence_score == 100:
        errors.append("Dry run must not report score 100")

    if errors:
        print("Self-test FAILED:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return EXIT_ERROR

    print("Self-test passed")
    print(f"  Probes in registry: {len(list_probes())}")
    print(f"  Providers: {len(list_providers())}")
    print(f"  Mock verification status: {report.verification_status.value}")
    return EXIT_SUCCESS


def cmd_probes_list(_args: argparse.Namespace) -> int:
    for probe in list_probes():
        print(f"{probe.id:25} {probe.category.value:14} {probe.language:4} {probe.severity.value}")
    return EXIT_SUCCESS


def cmd_probes_show(args: argparse.Namespace) -> int:
    probe = get_probe(args.probe_id)
    if not probe:
        print(f"Unknown probe: {args.probe_id}", file=sys.stderr)
        return EXIT_ERROR
    print(json.dumps(probe.model_dump(mode="json"), indent=2))
    return EXIT_SUCCESS


def cmd_providers_list(_args: argparse.Namespace) -> int:
    for info in list_providers():
        print(f"{info['name']:12} env_key={info['env_key']}")
    return EXIT_SUCCESS


def _run_self_test_checks() -> list[str]:
    errors: list[str] = []
    errors.extend(validate_registry())
    provider = get_provider("mock", expected_identity="claude")
    report = run_verification(provider, "mock-model", "claude", mode="quick", dry_run=False)
    if report.metrics.total_probes == 0:
        errors.append("No probes executed in self-test")
    return errors


def cmd_doctor(_args: argparse.Namespace) -> int:
    print(f"Python: {sys.version.split()[0]}")
    print(f"Package: model-identity-verifier {__version__}")

    for info in list_providers():
        env_key = info["env_key"]
        if env_key == "(none)":
            print(f"Provider {info['name']}: no API key required")
        else:
            present = "set" if os.environ.get(env_key) else "not set"
            print(f"Provider {info['name']}: {env_key} {present}")

    optional = ["openai", "anthropic", "google.generativeai"]
    for module in optional:
        available = importlib.util.find_spec(module.split(".")[0]) is not None
        print(f"Optional dependency {module}: {'available' if available else 'not installed'}")

    reports_dir = Path(".miv/reports")
    try:
        reports_dir.mkdir(parents=True, exist_ok=True)
        test_file = reports_dir / ".write_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
        print(f"Report directory {reports_dir}: writable")
    except OSError as exc:
        print(f"Report directory {reports_dir}: not writable ({exc})")
        return EXIT_ERROR

    errors = _run_self_test_checks()
    if errors:
        print("Self-test issues:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return EXIT_ERROR

    print("Self-test: passed (no network)")
    return EXIT_SUCCESS


def cmd_baseline_create(args: argparse.Namespace) -> int:
    report_path = Path(args.report)
    if not report_path.exists():
        print(f"Report not found: {report_path}", file=sys.stderr)
        return EXIT_ERROR

    data = json.loads(report_path.read_text(encoding="utf-8"))
    report = VerificationReport.model_validate(data)
    baseline = baseline_from_report(report, baseline_id=args.baseline_id or "")
    if args.output:
        output = Path(args.output)
    else:
        output = Path(".miv/baselines") / f"{baseline.baseline_id}.json"
    save_baseline(baseline, output)
    print(f"Baseline saved to {output}")
    return EXIT_SUCCESS


def cmd_baseline_check(args: argparse.Namespace) -> int:
    baseline_path = Path(args.baseline)
    report_path = Path(args.report)
    if not baseline_path.exists():
        print(f"Baseline not found: {baseline_path}", file=sys.stderr)
        return EXIT_ERROR
    if not report_path.exists():
        print(f"Report not found: {report_path}", file=sys.stderr)
        return EXIT_ERROR

    baseline = load_baseline(baseline_path)
    report = VerificationReport.model_validate(json.loads(report_path.read_text(encoding="utf-8")))
    drift = check_drift(baseline, report)
    print(f"Drift status: {drift.status.value}")
    for warning in drift.warnings:
        print(f"  - {warning}")
    if drift.status.value in ("SIGNIFICANT", "SEVERE"):
        return EXIT_WARN
    return EXIT_SUCCESS


def cmd_reports_compare(args: argparse.Namespace) -> int:
    path_a = Path(args.report_a)
    path_b = Path(args.report_b)
    if not path_a.exists() or not path_b.exists():
        print("One or both report files not found", file=sys.stderr)
        return EXIT_ERROR

    report_a = VerificationReport.model_validate(json.loads(path_a.read_text(encoding="utf-8")))
    report_b = VerificationReport.model_validate(json.loads(path_b.read_text(encoding="utf-8")))
    comparison = compare_reports(report_a, report_b)
    print(json.dumps(comparison, indent=2))
    return EXIT_SUCCESS


def cmd_reports_inspect(args: argparse.Namespace) -> int:
    report_dir = Path(args.report_dir)
    if not report_dir.is_dir():
        print(f"Report directory not found: {report_dir}", file=sys.stderr)
        return EXIT_ERROR

    summaries = inspect_paths(report_dir, args.glob)
    if not summaries:
        print(f"No reports matched {args.glob} in {report_dir}", file=sys.stderr)
        return EXIT_FAIL

    print_inspection(summaries)
    return EXIT_SUCCESS


def cmd_reports_gate(args: argparse.Namespace) -> int:
    report_dir = Path(args.report_dir)
    if not report_dir.is_dir():
        print(f"Report directory not found: {report_dir}", file=sys.stderr)
        return EXIT_ERROR

    result = evaluate_gate(report_dir, release=args.release)
    print_gate_result(result)
    return gate_exit_code(result)


def cmd_providers_check(args: argparse.Namespace) -> int:
    try:
        provider = get_provider(args.provider)
    except ProviderError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_ERROR

    try:
        result = provider.validate_key()
    except MissingApiKeyError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_FAIL
    except InvalidApiKeyError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_ERROR
    except ProviderError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_ERROR

    print(json.dumps(result, indent=2))
    return EXIT_SUCCESS


def _write_output(content: str, output_path: Path | None) -> None:
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")


def cmd_prompt_create(args: argparse.Namespace) -> int:
    _warn_unknown_expected_identity(args.expected_identity)
    content = format_prompt_pack(args.expected_identity, args.mode, args.format)
    output_path = Path(args.output) if args.output else None
    if output_path:
        _write_output(content, output_path)
    else:
        print(content)
    return EXIT_SUCCESS


def cmd_prompt_template(args: argparse.Namespace) -> int:
    _warn_unknown_expected_identity(args.expected_identity)
    content = format_response_template(args.expected_identity, args.mode)
    output_path = Path(args.output) if args.output else None
    if output_path:
        _write_output(content, output_path)
    else:
        print(content)
    return EXIT_SUCCESS


def cmd_prompt_browser(args: argparse.Namespace) -> int:
    _warn_unknown_expected_identity(args.expected_identity)
    content = format_browser_prompt(args.expected_identity, args.mode)
    output_path = Path(args.output) if args.output else None
    if output_path:
        _write_output(content, output_path)
    else:
        print(content)
    return EXIT_SUCCESS


def cmd_prompt_assess(args: argparse.Namespace) -> int:
    if args.output and args.save:
        print("Error: --output and --save cannot be used together", file=sys.stderr)
        return EXIT_ERROR

    output_path = Path(args.output or args.save) if (args.output or args.save) else None
    _warn_unknown_expected_identity(args.expected_identity)

    if args.stdin:
        response_text = sys.stdin.read()
    elif args.response_file:
        response_path = Path(args.response_file)
        if not response_path.exists():
            print(f"Response file not found: {response_path}", file=sys.stderr)
            return EXIT_ERROR
        response_text = response_path.read_text(encoding="utf-8")
    else:
        print("Error: provide --response-file or --stdin", file=sys.stderr)
        return EXIT_ERROR

    report = run_manual_assessment(
        args.expected_identity,
        response_text,
        pack_mode=args.pack_mode,
        requested_model=args.model,
    )

    if output_path:
        suffix = output_path.suffix.lower()
        if suffix == ".json" or args.format == "json":
            save_json_report(report, output_path)
        elif suffix in (".md", ".markdown") or args.format == "markdown":
            save_markdown_report(report, output_path)
        else:
            save_json_report(report, output_path)

    if args.format == "json" and not output_path:
        print(json.dumps(report.model_dump(mode="json"), indent=2))
    elif args.format == "markdown" and not output_path:
        from model_identity_verifier.reports.markdown_report import render_markdown_report

        print(render_markdown_report(report))
    else:
        render_terminal_report(report)

    return _exit_code(report.verification_status)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="miv",
        description=(
            "Model Identity Verifier - detect suspicious model self-identification behavior. "
            "Model self-identification is generated text. It is not attestation."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    version_parser = subparsers.add_parser("version", help="Show version")
    version_parser.set_defaults(func=cmd_version)

    verify_parser = subparsers.add_parser("verify", help="Run identity verification")
    verify_parser.add_argument("--provider", default="mock", help="Provider name")
    verify_parser.add_argument("--model", default="mock-model", help="Model name")
    verify_parser.add_argument(
        "--expected-identity", default="claude", help="Expected model identity"
    )
    verify_parser.add_argument("--api-key", default=None, help="API key (prefer env vars)")
    verify_modes = ["quick", "stress", "deep", "route", "downgrade"]
    verify_parser.add_argument("--mode", default="quick", choices=verify_modes)
    verify_parser.add_argument("--quick", action="store_true", help="Alias for --mode quick")
    verify_parser.add_argument("--save", default=None, help="Alias for --output (report file path)")
    verify_parser.add_argument(
        "--dry-run", action="store_true", help="Plan probes without API calls"
    )
    verify_parser.add_argument(
        "--route-check", action="store_true", help="Include route metadata probes"
    )
    verify_parser.add_argument(
        "--downgrade-check", action="store_true", help="Include downgrade probes"
    )
    verify_parser.add_argument(
        "--format", default="terminal", choices=["terminal", "json", "markdown", "sarif"]
    )
    verify_parser.add_argument("--output", "-o", default=None, help="Output file path")
    verify_parser.set_defaults(func=cmd_verify)

    self_test_parser = subparsers.add_parser("self-test", help="Run internal self-test")
    self_test_parser.set_defaults(func=cmd_self_test)

    doctor_parser = subparsers.add_parser("doctor", help="Check local environment")
    doctor_parser.set_defaults(func=cmd_doctor)

    probes_parser = subparsers.add_parser("probes", help="Probe management")
    probes_sub = probes_parser.add_subparsers(dest="probes_command", required=True)

    probes_list = probes_sub.add_parser("list", help="List all probes")
    probes_list.set_defaults(func=cmd_probes_list)

    probes_show = probes_sub.add_parser("show", help="Show probe details")
    probes_show.add_argument("probe_id", help="Probe ID")
    probes_show.set_defaults(func=cmd_probes_show)

    providers_parser = subparsers.add_parser("providers", help="Provider management")
    providers_sub = providers_parser.add_subparsers(dest="providers_command", required=True)

    providers_list = providers_sub.add_parser("list", help="List providers")
    providers_list.set_defaults(func=cmd_providers_list)

    providers_check = providers_sub.add_parser("check", help="Validate provider API key")
    providers_check.add_argument(
        "--provider",
        required=True,
        choices=["openrouter"],
        help="Provider to validate (network call for OpenRouter)",
    )
    providers_check.set_defaults(func=cmd_providers_check)

    baseline_parser = subparsers.add_parser("baseline", help="Baseline management")
    baseline_sub = baseline_parser.add_subparsers(dest="baseline_command", required=True)

    baseline_create = baseline_sub.add_parser("create", help="Create baseline from report")
    baseline_create.add_argument("--report", required=True, help="Source report JSON path")
    baseline_create.add_argument("--output", default=None, help="Baseline output path")
    baseline_create.add_argument("--baseline-id", default=None, help="Baseline identifier")
    baseline_create.set_defaults(func=cmd_baseline_create)

    baseline_check = baseline_sub.add_parser("check", help="Check report against baseline")
    baseline_check.add_argument("--baseline", required=True, help="Baseline JSON path")
    baseline_check.add_argument("--report", required=True, help="Report JSON path")
    baseline_check.set_defaults(func=cmd_baseline_check)

    reports_parser = subparsers.add_parser("reports", help="Report utilities")
    reports_sub = reports_parser.add_subparsers(dest="reports_command", required=True)

    reports_compare = reports_sub.add_parser("compare", help="Compare two reports")
    reports_compare.add_argument("report_a", help="First report JSON path")
    reports_compare.add_argument("report_b", help="Second report JSON path")
    reports_compare.set_defaults(func=cmd_reports_compare)

    reports_inspect = reports_sub.add_parser("inspect", help="Inspect smoke report summaries")
    reports_inspect.add_argument(
        "--report-dir",
        default=".miv/reports",
        help="Directory containing report JSON files",
    )
    reports_inspect.add_argument(
        "--glob",
        default="*v013-smoke.json",
        help="Glob pattern for reports to inspect",
    )
    reports_inspect.set_defaults(func=cmd_reports_inspect)

    reports_gate = reports_sub.add_parser("gate", help="Evaluate v0.1.3 live smoke release gate")
    reports_gate.add_argument(
        "--report-dir",
        default=".miv/reports",
        help="Directory containing required smoke JSON files",
    )
    reports_gate.add_argument("--release", default="v0.1.3", help="Release version label")
    reports_gate.set_defaults(func=cmd_reports_gate)

    prompt_parser = subparsers.add_parser(
        "prompt",
        help="Manual prompt-mode integrity checks (no API calls)",
    )
    prompt_sub = prompt_parser.add_subparsers(dest="prompt_command", required=True)

    prompt_create = prompt_sub.add_parser("create", help="Generate manual prompt pack")
    prompt_create.add_argument(
        "--expected-identity", default="chatgpt", help="Expected model identity"
    )
    prompt_create_modes = ["quick", "standard", "deep"]
    prompt_create.add_argument("--mode", default="quick", choices=prompt_create_modes)
    prompt_create.add_argument(
        "--format",
        default="text",
        choices=["text", "markdown", "json", "browser"],
    )
    prompt_create.add_argument("--output", "-o", default=None, help="Output file path")
    prompt_create.set_defaults(func=cmd_prompt_create)

    prompt_template = prompt_sub.add_parser(
        "template", help="Generate response collection template"
    )
    prompt_template.add_argument(
        "--expected-identity", default="chatgpt", help="Expected model identity"
    )
    prompt_template.add_argument("--mode", default="quick", choices=prompt_create_modes)
    prompt_template.add_argument("--output", "-o", default=None, help="Output file path")
    prompt_template.set_defaults(func=cmd_prompt_template)

    prompt_browser = prompt_sub.add_parser(
        "browser",
        help="Generate single browser paste prompt for manual integrity suite",
    )
    prompt_browser.add_argument(
        "--expected-identity", default="chatgpt", help="Expected model identity"
    )
    prompt_browser.add_argument("--mode", default="quick", choices=prompt_create_modes)
    prompt_browser.add_argument("--output", "-o", default=None, help="Output file path")
    prompt_browser.set_defaults(func=cmd_prompt_browser)

    prompt_assess = prompt_sub.add_parser("assess", help="Assess pasted model responses")
    prompt_assess.add_argument(
        "--expected-identity", default="chatgpt", help="Expected model identity"
    )
    prompt_assess.add_argument(
        "--pack-mode",
        default=None,
        choices=prompt_create_modes,
        help="Prompt-pack assessment (requires one response per prompt)",
    )
    prompt_assess.add_argument("--model", default=None, help="User-supplied model label")
    prompt_assess.add_argument("--response-file", default=None, help="Response text file")
    prompt_assess.add_argument("--stdin", action="store_true", help="Read response from stdin")
    prompt_assess.add_argument(
        "--format", default="terminal", choices=["terminal", "json", "markdown"]
    )
    prompt_assess.add_argument("--output", "-o", default=None, help="Output report path")
    prompt_assess.add_argument("--save", default=None, help="Alias for --output")
    prompt_assess.set_defaults(func=cmd_prompt_assess)

    return parser


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)
    exit_code = args.func(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
