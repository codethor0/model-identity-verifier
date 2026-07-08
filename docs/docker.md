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

## Notes

- The image installs the package with dev dependencies for validation.
- `.env`, `.miv`, `dist`, and `build` are excluded via `.dockerignore`.
- Live provider verification still requires API keys on the host, not inside the default image.
