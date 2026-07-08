# Release Checklist

## Pre-release validation

- [ ] `ruff format --check .` passes
- [ ] `ruff check .` passes
- [ ] `python -m pytest` passes (155+ tests)
- [ ] `python -m build` passes
- [ ] `twine check dist/*` passes
- [ ] `miv self-test` passes
- [ ] `miv verify --dry-run` shows INCONCLUSIVE
- [ ] `bash scripts/e2e_local.sh` passes
- [ ] `docker build -t model-identity-verifier:v0.1.3 .` passes

## Live provider smoke tests

Required before tagging. Prefer hidden terminal input; do not write keys to disk.
Do not store release smoke keys in `.env`. Export them in the current shell session only,
or use `read -s` via the runbook scripts below.

OpenAI `429 insufficient_quota` is external API Platform billing/quota, not a tool defect.
ChatGPT subscription billing is separate from OpenAI API Platform credits.

Manual/browser prompt reports (`manual_mode=true`) are integrity testing only and cannot
satisfy the live provider smoke gate for v0.1.3.

Interactive Docker gate (recommended):

```bash
bash scripts/run_live_smoke_interactive.sh
```

Local runbook with `read -s` key entry and gate review:

```bash
bash scripts/run_local_smoke_runbook.sh
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
miv reports inspect --glob '*v013-smoke.json'
miv reports gate --release v0.1.3
```

### Smoke scripts

| Script | Purpose | Gate-eligible |
| --- | --- | --- |
| `scripts/run_local_smoke_runbook.sh` | Full local live smoke with `read -s` keys | yes |
| `scripts/run_live_smoke_interactive.sh` | Docker live smoke + gate review | yes |
| `scripts/e2e_docker_live.sh` | Docker live smoke only | yes |
| `scripts/run_openai_smoke_interactive.sh` | OpenAI-only partial smoke | partial |
| `scripts/run_anthropic_smoke_interactive.sh` | Anthropic-only partial smoke | partial |
| `scripts/run_remaining_smoke_interactive.sh` | OpenAI + OpenRouter partial smoke | partial |
| `scripts/run_openai_prompt_smoke.sh` | Manual/browser prompt workflow | no (`manual_mode=true`) |
| `scripts/post_smoke_tag_gate.sh` | Review existing live smoke reports | review only |

OpenRouter key validation before smoke:

```bash
miv providers check --provider openrouter
```

Manual per-provider commands (if not using the script):

```bash
mkdir -p .miv/reports

miv verify --provider openai --model gpt-4o-mini --expected-identity chatgpt \
  --quick --format json --save .miv/reports/openai-v013-smoke.json

miv verify --provider anthropic --model claude-sonnet-4-6 --expected-identity claude \
  --quick --format json --save .miv/reports/anthropic-v013-smoke.json

miv verify --provider openrouter --model openai/gpt-4o-mini --expected-identity chatgpt \
  --route-check --quick --format json --save .miv/reports/openrouter-v013-smoke.json
```

Required providers for full v0.1.3 gate: OpenAI, Anthropic, OpenRouter.

v0.1.3 remains held until all three live smoke reports are present and acceptable.
Do not tag while OpenAI quota is blocked or OpenRouter smoke is missing.

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
