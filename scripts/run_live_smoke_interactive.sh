#!/usr/bin/env bash
# Interactive live provider smoke gate. Keys via read -s only; never written to disk.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

unset OPENAI_API_KEY ANTHROPIC_API_KEY OPENROUTER_API_KEY

printf "Paste OpenAI API key, then press Enter: "
read -s OPENAI_API_KEY
printf "\n"

printf "Paste Anthropic API key, then press Enter: "
read -s ANTHROPIC_API_KEY
printf "\n"

printf "Paste OpenRouter API key (or press Enter to skip): "
read -s OPENROUTER_API_KEY
printf "\n"

export OPENAI_API_KEY ANTHROPIC_API_KEY OPENROUTER_API_KEY

python3 - <<'PY'
import os

for name in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"]:
    print(f"{name}: {'set' if os.getenv(name) else 'missing'}")
PY

set +e
bash scripts/e2e_docker_live.sh
SMOKE_EXIT=$?
set -e

echo "Docker live smoke exit code: $SMOKE_EXIT"

unset OPENAI_API_KEY ANTHROPIC_API_KEY OPENROUTER_API_KEY

python3 - <<'PY'
import os

for name in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"]:
    print(f"{name}: {'set' if os.getenv(name) else 'missing'}")
PY

exit "$SMOKE_EXIT"
