# Contributing

Thank you for contributing to Model Identity Verifier.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quality checks

Before submitting a pull request, ensure all checks pass:

```bash
ruff format --check .
ruff check .
python -m pytest
python -m build
miv self-test
miv verify --dry-run
```

## Guidelines

- Keep changes focused and minimal
- Add tests for behavior users depend on
- No network calls in unit tests
- No secrets in code or reports
- No prompt artifacts in any file
- No emojis in code, docs, or output
- Document only implemented features
- Use careful language: detected, suspected, observed (not proven, guaranteed)

## Pull requests

1. Fork the repository
2. Create a feature branch
3. Add tests for your changes
4. Ensure all quality checks pass
5. Submit a pull request with a clear description

## Branch strategy

This project uses trunk-based development.

- `main` is the only long-lived branch.
- Use short-lived `feature/<name>` or `fix/<name>` branches for focused work.
- Delete branches after merge.
- Use signed tags for releases.
- Do not keep stale experiment branches in the public repository.
- Do not force-push `main`.

## Probes

New probes must include: id, prompt, language, category, subcategory, expected_behavior, severity, tags, and notes. Probe IDs must be unique.

## Reporting issues

Use GitHub issues for bugs and feature requests. For security issues, see [SECURITY.md](SECURITY.md).
