# Security Policy

## Reporting a vulnerability

If you discover a security vulnerability, please report it responsibly. Do not open a public issue for security-sensitive findings.

Report security issues via GitHub Security Advisories or by contacting the maintainers through the repository issue tracker with the subject prefix `[SECURITY]`.

## Scope

This tool interacts with third-party LLM APIs using user-supplied credentials. Security considerations include:

- API key handling (environment variables, never written to disk)
- Secret redaction in errors and reports
- Network timeouts and bounded retries
- Supply chain dependencies

## API keys

- Store keys in environment variables or `.env` (never commit `.env`)
- Keys are never included in reports or logs
- Keys are redacted from error messages

## Reports

Verification reports may contain model response text. Review reports before sharing externally. Use output redaction when sharing reports in public channels.

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |

## Security tooling

The project uses `pip-audit` and `bandit` in CI. Dependabot is recommended for dependency updates.
