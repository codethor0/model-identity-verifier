# Release Checklist

## Pre-release validation

- [ ] `ruff format --check .` passes
- [ ] `ruff check .` passes
- [ ] `python -m pytest` passes (135+ tests)
- [ ] `python -m build` passes
- [ ] `twine check dist/*` passes
- [ ] `miv self-test` passes
- [ ] `miv verify --dry-run` shows INCONCLUSIVE
- [ ] `bash scripts/e2e_local.sh` passes
- [ ] `docker build -t model-identity-verifier:v0.1.3 .` passes

## Live provider smoke tests

Required before tagging. Prefer hidden terminal input; do not write keys to disk.

Interactive Docker gate (recommended):

```bash
bash scripts/run_live_smoke_interactive.sh
```

Or export keys in the current shell session only, then:

```bash
bash scripts/e2e_docker_live.sh
```

Exit codes:

- `0` — live smoke passed
- `2` — Docker OK, keys missing
- `1` — failure; do not tag

After successful live smoke, review tag readiness:

```bash
bash scripts/post_smoke_tag_gate.sh
```

Manual per-provider commands (if not using the script):

```bash
mkdir -p .miv/reports

miv verify --provider openai --model gpt-4o-mini --expected-identity chatgpt \
  --quick --format json --save .miv/reports/openai-v013-smoke.json

miv verify --provider anthropic --model claude-3-5-sonnet-20241022 --expected-identity claude \
  --quick --format json --save .miv/reports/anthropic-v013-smoke.json

miv verify --provider openrouter --model openai/gpt-4o-mini --expected-identity chatgpt \
  --route-check --quick --format json --save .miv/reports/openrouter-v013-smoke.json
```

Required providers for full v0.1.3 gate: OpenAI, Anthropic, OpenRouter.

## Secret check

```bash
grep -R "sk-\|sk-ant-\|sk-proj-\|Bearer\|API_KEY\|Authorization\|x-api-key" .miv/reports || echo "clean"
```

Reports must be clean before sharing. Do not commit `.miv/reports`.

## Tag and publish (after live smoke passes)

```bash
git status --short
git log --format='%an <%ae> | %cn <%ce>' --all
git tag -s v0.1.3 -m "v0.1.3"
git push origin main
git push origin v0.1.3
```

Do not tag while live smoke is blocked or reports contain secrets.

Model self-identification is generated text. It is not attestation.
