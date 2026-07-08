# Changelog

All notable changes to this project will be documented in this file.

## [0.1.1] - 2026-07-08

### Fixed

- Dry run now reports INCONCLUSIVE with score N/A instead of misleading PASS/100
- All-skipped reports are INCONCLUSIVE with structured finding

### Added

- Claim-level identity evidence with mixed-claim support
- Structured `score_findings` ledger in reports
- Report schema/scoring/detector/probe-set version metadata
- Stronger secret redaction (query strings, headers, nested metadata)
- Route metadata match types: exact, alias, mismatch, missing, opaque
- CLI `--quick` and `--save` aliases
- `miv doctor` environment check command
- Improved `reports compare` output
- Dependabot configuration
- CI Python 3.10-3.12 matrix

### Changed

- Documentation updated for PASS semantics, dry run, and exit codes

## [0.1.0] - 2026-07-08

### Added

- Initial release of Model Identity Verifier CLI (`miv`)
- Identity detection engine with multilingual and boundary-case support
- Probe registry with base, multilingual, adversarial, stress, route, and downgrade probes
- Weighted scoring with explainable status determination
- Provider adapters: mock, OpenAI, Anthropic, DeepSeek, Gemini, OpenRouter
- Report formats: terminal, JSON, Markdown, SARIF
- Baseline create/check and report comparison
- Self-test command with no network calls
