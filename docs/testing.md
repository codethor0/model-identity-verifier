# Testing

## Unit and integration tests

```bash
ruff format --check .
ruff check .
python -m pytest
```

## Local end-to-end script

`scripts/e2e_local.sh` runs formatting, lint, tests, build, self-test, dry-run, doctor, and manual prompt-mode checks without API keys.

```bash
bash scripts/e2e_local.sh
```

Dry-run exit code 1 is accepted as expected when status is INCONCLUSIVE.

## Docker validation

See [docker.md](docker.md).

## Live provider smoke

Live API tests require provider keys and are not run in CI. See [release-checklist.md](release-checklist.md).

## Manual prompt fixtures

Response fixtures for manual mode live under `tests/fixtures/manual/`.
