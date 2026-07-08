# Release Checklist

## Pre-release validation

- [ ] `ruff format --check .` passes
- [ ] `ruff check .` passes
- [ ] `python -m pytest` passes (99+ tests)
- [ ] `python -m build` passes
- [ ] `miv self-test` passes
- [ ] `miv verify --dry-run` shows INCONCLUSIVE

## Live provider smoke tests

Run with real API keys:

```bash
export OPENAI_API_KEY="your-key"
miv verify --provider openai --model gpt-4o-mini --expected-identity chatgpt \
  --mode quick --format json -o .miv/reports/openai-quick.json

export ANTHROPIC_API_KEY="your-key"
miv verify --provider anthropic --model claude-3-5-sonnet-20241022 --expected-identity claude \
  --mode quick --format json -o .miv/reports/anthropic-quick.json

export OPENROUTER_API_KEY="your-key"
miv verify --provider openrouter --model openai/gpt-4o-mini --expected-identity chatgpt \
  --route-check --mode quick --format json -o .miv/reports/openrouter-route.json
```

## Secret check

```bash
grep -R "sk-" .miv/reports || true
grep -R "API_KEY" .miv/reports || true
```

## Git push

```bash
git status --short
git log --format='%an <%ae> | %cn <%ce>' --all
git tag -s v0.1.2 -m "v0.1.2"
git push origin main
git push origin v0.1.2
```

Model self-identification is generated text. It is not attestation.
