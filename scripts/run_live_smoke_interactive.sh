#!/usr/bin/env bash
# Interactive live provider smoke gate. Keys via read -s only; never written to disk.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

require_key() {
  local name="$1"
  local label="$2"
  local value=""
  while [ -z "$value" ]; do
    printf "Paste %s, then press Enter: " "$label"
    read -s value
    printf "\n"
    if [ -z "$value" ]; then
      echo "  $name is required for full v0.1.3 gate." >&2
    fi
  done
  printf -v "$name" '%s' "$value"
}

unset OPENAI_API_KEY ANTHROPIC_API_KEY OPENROUTER_API_KEY

require_key OPENAI_API_KEY "OpenAI API key"
require_key ANTHROPIC_API_KEY "Anthropic API key"

printf "Paste OpenRouter API key (required for full gate, or press Enter to skip): "
read -s OPENROUTER_API_KEY
printf "\n"

export OPENAI_API_KEY ANTHROPIC_API_KEY OPENROUTER_API_KEY

python3 - <<'PY'
import os

for name in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"]:
    print(f"{name}: {'set' if os.getenv(name) else 'missing'}")
PY

if [ -z "${OPENROUTER_API_KEY:-}" ]; then
  echo "WARNING: OPENROUTER_API_KEY missing — partial smoke only; full tag gate requires OpenRouter." >&2
fi

set +e
bash scripts/e2e_docker_live.sh
SMOKE_EXIT=$?
set -e

echo "Docker live smoke exit code: $SMOKE_EXIT"

if compgen -G ".miv/reports/*v013-smoke.json" >/dev/null; then
  bash scripts/post_smoke_tag_gate.sh
  TAG_EXIT=$?
  echo "Tag gate exit code: $TAG_EXIT"
fi

unset OPENAI_API_KEY ANTHROPIC_API_KEY OPENROUTER_API_KEY

python3 - <<'PY'
import os

for name in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"]:
    print(f"{name}: {'set' if os.getenv(name) else 'missing'}")
PY

exit "$SMOKE_EXIT"
