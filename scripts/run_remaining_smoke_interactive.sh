#!/usr/bin/env bash
# OpenAI + OpenRouter live smoke for v0.1.3. Keys via read -s only; never written to disk.
# Anthropic already passed; this does not rerun Anthropic.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate

mkdir -p .miv/reports
rm -f .miv/reports/openai-v013-smoke.json .miv/reports/openrouter-v013-smoke.json

unset OPENAI_API_KEY OPENROUTER_API_KEY

while [ -z "${OPENAI_API_KEY:-}" ]; do
  printf "Paste OpenAI API key, then press Enter: "
  read -s OPENAI_API_KEY
  printf "\n"
  [ -z "${OPENAI_API_KEY:-}" ] && echo "OPENAI_API_KEY is required." >&2
done

while [ -z "${OPENROUTER_API_KEY:-}" ]; do
  printf "Paste OpenRouter API key, then press Enter: "
  read -s OPENROUTER_API_KEY
  printf "\n"
  [ -z "${OPENROUTER_API_KEY:-}" ] && echo "OPENROUTER_API_KEY is required for full gate." >&2
done

export OPENAI_API_KEY OPENROUTER_API_KEY

python3 - <<'PY'
import os
for name in ["OPENAI_API_KEY", "OPENROUTER_API_KEY"]:
    print(f"{name}: {'set' if os.getenv(name) else 'missing'}")
PY

echo "==> OpenRouter key validation (/api/v1/key)"
OPENROUTER_KEY_OK=0
python3 - <<'PY'
import json
import os
import sys
import tempfile
from pathlib import Path

import httpx

key = os.getenv("OPENROUTER_API_KEY")
if not key:
    print("OPENROUTER_API_KEY: missing")
    sys.exit(2)

tmp = Path(tempfile.mkstemp(prefix="openrouter-key-check-", suffix=".json")[1])
try:
    response = httpx.get(
        "https://openrouter.ai/api/v1/key",
        headers={"Authorization": f"Bearer {key}"},
        timeout=30.0,
    )
    tmp.write_text(response.text)
    print("OpenRouter key validation HTTP status:", response.status_code)
    if response.status_code != 200:
        print("OpenRouter key validation failed. Do not run OpenRouter smoke yet.")
        sys.exit(1)
    data = response.json()
    info = data.get("data", {})
    print("OpenRouter key active:", bool(info))
    print("OpenRouter limit_remaining_present:", "limit_remaining" in info)
    print("OpenRouter is_free_tier:", info.get("is_free_tier"))
    print("OpenRouter disabled:", info.get("disabled"))
finally:
    tmp.unlink(missing_ok=True)

print("OpenRouter key validation passed.")
PY
OPENROUTER_KEY_OK=$?

if [ "$OPENROUTER_KEY_OK" -ne 0 ]; then
  echo "OpenRouter auth validation failed. Fix key before OpenRouter smoke." >&2
  unset OPENAI_API_KEY OPENROUTER_API_KEY
  exit 1
fi

echo "==> OpenAI smoke (requires fixed API billing/quota)"
set +e
miv verify \
  --provider openai \
  --model gpt-4o-mini \
  --expected-identity chatgpt \
  --quick \
  --format json \
  --save .miv/reports/openai-v013-smoke.json
OPENAI_EXIT=$?
echo "OpenAI smoke exit code: $OPENAI_EXIT"

if [ -f .miv/reports/openai-v013-smoke.json ] && grep -q insufficient_quota .miv/reports/openai-v013-smoke.json; then
  echo "OPENAI V0.1.3 LIVE SMOKE BLOCKED — insufficient_quota" >&2
fi

echo "==> OpenRouter smoke (key validation passed)"
miv verify \
  --provider openrouter \
  --model openai/gpt-4o-mini \
  --expected-identity chatgpt \
  --route-check \
  --quick \
  --format json \
  --save .miv/reports/openrouter-v013-smoke.json
OPENROUTER_EXIT=$?
echo "OpenRouter smoke exit code: $OPENROUTER_EXIT"
set -e

echo "==> secret scan"
if grep -E "sk-proj-[a-zA-Z0-9]{20,}|sk-ant-[a-zA-Z0-9]{20,}|sk-or-[a-zA-Z0-9]{20,}|sk-[a-zA-Z0-9]{32,}|Bearer sk-|(OPENAI|ANTHROPIC|OPENROUTER)_API_KEY=[^[:space:]]+" .miv/reports/*v013-smoke.json 2>/dev/null; then
  echo "SECRET SCAN: LEAKED"
else
  echo "SECRET SCAN: clean"
fi

echo "==> inspect all provider reports"
python3 - <<'PY'
import json
from pathlib import Path

for path in sorted(Path(".miv/reports").glob("*v013-smoke.json")):
    data = json.loads(path.read_text())
    print(path.name)
    print("  provider:", data.get("provider"))
    print("  requested_model:", data.get("requested_model"))
    print("  expected_identity:", data.get("expected_identity"))
    print("  dry_run:", data.get("dry_run"))
    print("  manual_mode:", data.get("manual_mode"))
    print("  verification_status:", data.get("verification_status"))
    print("  confidence_score:", data.get("confidence_score"))
    print("  risk_level:", data.get("risk_level"))
    print("  schema_version:", data.get("schema_version"))
    print("  warnings:", data.get("warnings"))
    print("  errors:", data.get("errors"))
    print("  score_findings:", [f.get("id") for f in data.get("score_findings", [])])
    print()
PY

echo "==> gitignore check"
git status --short
for f in openai anthropic openrouter; do
  p=".miv/reports/${f}-v013-smoke.json"
  [ -f "$p" ] && git check-ignore -v "$p" || true
done

unset OPENAI_API_KEY OPENROUTER_API_KEY
python3 - <<'PY'
import os
for name in ["OPENAI_API_KEY", "OPENROUTER_API_KEY"]:
    print(f"{name}: {'set' if os.getenv(name) else 'missing'}")
PY
