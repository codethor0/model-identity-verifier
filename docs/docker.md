# Docker validation

Docker provides a clean environment for smoke-testing the CLI without local virtualenv state.

## Build

```bash
docker build -t model-identity-verifier:e2e .
```

## Smoke commands

```bash
docker run --rm model-identity-verifier:e2e miv --help
docker run --rm model-identity-verifier:e2e miv version
docker run --rm model-identity-verifier:e2e miv self-test
docker run --rm model-identity-verifier:e2e miv verify --dry-run || true
docker run --rm model-identity-verifier:e2e miv probes list
docker run --rm model-identity-verifier:e2e miv providers list
docker run --rm model-identity-verifier:e2e miv prompt create --expected-identity chatgpt --mode quick
```

No API keys are required for these commands.

## Live provider smoke (Docker)

Keys are passed from the host shell into the container via `-e` environment variables. They are never written to the image or repo.

```bash
bash scripts/run_live_smoke_interactive.sh
```

This prompts for keys with hidden input (`read -s`), runs `scripts/e2e_docker_live.sh`, scans reports for secrets, prints inspection output, and clears keys from the shell.

If keys are already exported in the current session:

```bash
bash scripts/e2e_docker_live.sh
```

Exit codes: `0` pass, `2` keys missing, `1` failure.

## Notes

- The image installs the package with dev dependencies for validation.
- `.env`, `.miv`, `dist`, and `build` are excluded via `.dockerignore`.
- Live provider verification requires user-supplied keys on the host; reports are written to `.miv/reports` via a bind mount and are gitignored.
