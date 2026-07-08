#!/usr/bin/env bash
# Local live smoke runbook for v0.1.3. Keys via read -s only; never written to disk.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate

mkdir -p .miv/reports

unset OPENAI_API_KEY ANTHROPIC_API_KEY OPENROUTER_API_KEY

while [ -z "${OPENAI_API_KEY:-}" ]; do
  printf "Paste OpenAI API key, then press Enter: "
  read -s OPENAI_API_KEY
  printf "\n"
  [ -z "${OPENAI_API_KEY:-}" ] && echo "OPENAI_API_KEY is required." >&2
done

while [ -z "${ANTHROPIC_API_KEY:-}" ]; do
  printf "Paste Anthropic API key, then press Enter: "
  read -s ANTHROPIC_API_KEY
  printf "\n"
  [ -z "${ANTHROPIC_API_KEY:-}" ] && echo "ANTHROPIC_API_KEY is required." >&2
done

while [ -z "${OPENROUTER_API_KEY:-}" ]; do
  printf "Paste OpenRouter API key, then press Enter: "
  read -s OPENROUTER_API_KEY
  printf "\n"
  [ -z "${OPENROUTER_API_KEY:-}" ] && echo "OPENROUTER_API_KEY is required." >&2
done

export OPENAI_API_KEY ANTHROPIC_API_KEY OPENROUTER_API_KEY

python3 -c "
import os
for name in ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'OPENROUTER_API_KEY']:
    print(f'{name}: {\"set\" if os.getenv(name) else \"missing\"}')"
"

echo "==> OpenRouter key validation"
miv providers check --provider openrouter

echo "==> OpenAI live smoke"
miv verify --provider openai --model gpt-4o-mini --expected-identity chatgpt \
  --quick --format json --save .miv/reports/openai-v013-smoke.json

echo "==> Anthropic live smoke"
miv verify --provider anthropic --model claude-sonnet-4-6 --expected-identity claude \
  --quick --format json --save .miv/reports/anthropic-v013-smoke.json

echo "==> OpenRouter live smoke"
miv verify --provider openrouter --model openai/gpt-4o-mini --expected-identity chatgpt \
  --route-check --quick --format json --save .miv/reports/openrouter-v013-smoke.json

echo "==> secret scan"
if grep -R "sk-\|Bearer\|API_KEY\|Authorization" .miv/reports/*v013-smoke.json 2>/dev/null; then
  echo "FAILED: possible secret leakage in smoke reports" >&2
  unset OPENAI_API_KEY ANTHROPIC_API_KEY OPENROUTER_API_KEY
  exit 1
fi
echo "clean"

echo "==> inspect reports"
miv reports inspect --glob '*v013-smoke.json'

echo "==> tag gate"
miv reports gate --release v0.1.3

unset OPENAI_API_KEY ANTHROPIC_API_KEY OPENROUTER_API_KEY
echo "Keys cleared from shell."
