#!/usr/bin/env bash
# OpenAI-only live smoke for v0.1.3. Key via read -s only; never written to disk.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate

mkdir -p .miv/reports
rm -f .miv/reports/openai-v013-smoke.json

unset OPENAI_API_KEY

while [ -z "${OPENAI_API_KEY:-}" ]; do
  printf "Paste OpenAI API key, then press Enter: "
  read -s OPENAI_API_KEY
  printf "\n"
  [ -z "${OPENAI_API_KEY:-}" ] && echo "OPENAI_API_KEY is required." >&2
done

export OPENAI_API_KEY
python3 - <<'PY'
import os
print("OPENAI_API_KEY:", "set" if os.getenv("OPENAI_API_KEY") else "missing")
PY

echo "==> OpenAI smoke (requires API billing/quota active)"
set +e
miv verify \
  --provider openai \
  --model gpt-4o-mini \
  --expected-identity chatgpt \
  --quick \
  --format json \
  --save .miv/reports/openai-v013-smoke.json
OPENAI_EXIT=$?
set -e
echo "OpenAI smoke exit code: $OPENAI_EXIT"

if [ -f .miv/reports/openai-v013-smoke.json ] && grep -q insufficient_quota .miv/reports/openai-v013-smoke.json; then
  echo "OPENAI V0.1.3 LIVE SMOKE BLOCKED — insufficient_quota" >&2
fi

if [ -f .miv/reports/openai-v013-smoke.json ]; then
  if grep -E "sk-proj-[a-zA-Z0-9]{20,}|Bearer sk-|OPENAI_API_KEY=[^[:space:]]+" .miv/reports/openai-v013-smoke.json 2>/dev/null; then
    echo "SECRET SCAN: LEAKED"
  else
    echo "SECRET SCAN: clean"
  fi

  python3 - <<'PY'
import json
from pathlib import Path

path = Path(".miv/reports/openai-v013-smoke.json")
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
PY

  git check-ignore -v .miv/reports/openai-v013-smoke.json || true
fi

unset OPENAI_API_KEY
python3 - <<'PY'
import os
print("OPENAI_API_KEY:", "set" if os.getenv("OPENAI_API_KEY") else "missing")
PY

exit "$OPENAI_EXIT"
