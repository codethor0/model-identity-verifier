# Agent rules

Stable repository rules for automated and human contributors.

## Before finishing work

- Run `ruff format --check .`
- Run `ruff check .`
- Run `python -m pytest`
- Run `miv self-test`
- Run `miv verify --dry-run`

## Code standards

- Use src layout (`src/model_identity_verifier`)
- Use typed Python with Pydantic models for structured data
- Use Ruff for linting and formatting
- No prompt artifacts in any file
- No emojis in code, docs, or output
- No secrets in code or reports
- No fake features or placeholder logic
- No live network calls in tests
- Keep docs aligned with implemented CLI behavior

## Product truth

Model self-identification is generated text. It is not attestation.

Do not overclaim. Use: detected, suspected, observed, reported.

## Scope

This is a focused Python CLI tool. Do not add web apps, databases, dashboards, or unrelated features.
