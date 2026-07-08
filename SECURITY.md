# Security Policy

## Reporting a vulnerability

If you discover a security vulnerability, please report it responsibly.

- Do not open a public issue for security-sensitive findings.
- Do not include API keys in issues or pull requests.
- Report suspected secret leakage privately via GitHub Security Advisories or a `[SECURITY]`-prefixed private report to maintainers.

## Scope

This tool interacts with third-party LLM APIs using user-supplied credentials. Security considerations include:

- API key handling (environment variables preferred)
- Secret redaction in errors, metadata, and reports
- Network timeouts and bounded retries
- Supply chain dependencies

## API keys

- Store keys in environment variables (recommended) or local `.env` (never commit `.env`)
- CLI `--api-key` is supported but less safe than environment variables
- Keys are redacted from error messages and provider metadata before storage
- Keys are never included in reports or logs by design

## Reports

Verification reports may contain model response text. Redact reports before sharing externally. Review JSON/Markdown/SARIF output for sensitive content before posting in public channels.

## Telemetry

This tool does not collect telemetry by default. Live provider tests require user-supplied credentials and make network calls only when you run verification without `--dry-run`.

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |

## Security tooling

The project uses `pip-audit` and `bandit` in CI. Dependabot monitors pip and GitHub Actions dependencies weekly.
