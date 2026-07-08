#!/usr/bin/env bash
# Anthropic-only live smoke for v0.1.3. Key via read -s only; never written to disk.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate

mkdir -p .miv/reports
rm -f .miv/reports/anthropic-v013-smoke.json \
  .miv/reports/anthropic-v013-smoke.md \
  .miv/reports/anthropic-v013-smoke.sarif

unset ANTHROPIC_API_KEY

while [ -z "${ANTHROPIC_API_KEY:-}" ]; do
  printf "Paste Anthropic API key, then press Enter: "
  read -s ANTHROPIC_API_KEY
  printf "\n"
  if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    echo "ANTHROPIC_API_KEY is required." >&2
  fi
done

export ANTHROPIC_API_KEY
python3 - <<'PY'
import os
print("ANTHROPIC_API_KEY:", "set" if os.getenv("ANTHROPIC_API_KEY") else "missing")
PY

set +e
miv verify \
  --provider anthropic \
  --model claude-sonnet-4-6 \
  --expected-identity claude \
  --quick \
  --format json \
  --save .miv/reports/anthropic-v013-smoke.json
ANTHROPIC_EXIT=$?
set -e

echo "Anthropic smoke exit code: $ANTHROPIC_EXIT"

if [ -f .miv/reports/anthropic-v013-smoke.json ]; then
  if grep -E "sk-ant-[a-zA-Z0-9]{20,}|Bearer sk-|ANTHROPIC_API_KEY=[^[:space:]]+" .miv/reports/anthropic-v013-smoke.json 2>/dev/null; then
    echo "SECRET SCAN: leaked"
  else
    echo "SECRET SCAN: clean"
  fi

  python3 - <<'PY'
import json
from pathlib import Path

path = Path(".miv/reports/anthropic-v013-smoke.json")
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
print("  detector_version:", data.get("detector_version"))
print("  scoring_version:", data.get("scoring_version"))
print("  probe_set_version:", data.get("probe_set_version"))
print("  warnings:", data.get("warnings"))
print("  errors:", data.get("errors"))
print("  score_findings:", [f.get("id") for f in data.get("score_findings", [])])
PY

  git check-ignore -v .miv/reports/anthropic-v013-smoke.json || true
fi

unset ANTHROPIC_API_KEY
python3 - <<'PY'
import os
print("ANTHROPIC_API_KEY:", "set" if os.getenv("ANTHROPIC_API_KEY") else "missing")
PY

exit "$ANTHROPIC_EXIT"
