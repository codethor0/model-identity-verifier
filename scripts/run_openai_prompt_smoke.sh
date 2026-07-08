#!/usr/bin/env bash
# OpenAI manual prompt-mode smoke for v0.1.3. No API key or billing required.
# Paste prompts into ChatGPT (web/app), collect responses, then assess locally.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate

REPORT_DIR="${ROOT}/.miv/reports"
PACK_FILE="${REPORT_DIR}/openai-chatgpt-prompt-pack.md"
TEMPLATE_FILE="${REPORT_DIR}/openai-chatgpt-response-template.txt"
RESPONSE_FILE="${REPORT_DIR}/openai-chatgpt-responses.txt"
REPORT_FILE="${REPORT_DIR}/openai-v013-prompt-smoke.json"

mkdir -p "$REPORT_DIR"
rm -f "$REPORT_FILE"

echo "==> OpenAI prompt-mode smoke (no API calls)"
echo "    Generate browser prompt with: miv prompt browser --expected-identity chatgpt --mode quick"

miv prompt browser \
  --expected-identity chatgpt \
  --mode quick \
  -o "$REPORT_DIR/openai-chatgpt-browser-prompt.txt"

miv prompt create \
  --expected-identity chatgpt \
  --mode quick \
  --format markdown \
  -o "$PACK_FILE"

miv prompt template \
  --expected-identity chatgpt \
  --mode quick \
  -o "$TEMPLATE_FILE"

echo
echo "Browser prompt: $REPORT_DIR/openai-chatgpt-browser-prompt.txt"
echo "Prompt pack:  $PACK_FILE"
echo "Template:     $TEMPLATE_FILE"
echo
echo "Next steps:"
echo "  1. Open the prompt pack and copy each prompt into ChatGPT."
echo "  2. Paste each model reply into the template (between ---MIV-RESPONSE--- lines)."
echo "  3. Save as: $RESPONSE_FILE"
echo "  4. Re-run this script and provide that file when prompted."
echo

if [ ! -f "$RESPONSE_FILE" ]; then
  printf "Path to completed response file [%s]: " "$RESPONSE_FILE"
  read -r user_path
  if [ -n "${user_path:-}" ]; then
    RESPONSE_FILE="$user_path"
  fi
fi

if [ ! -f "$RESPONSE_FILE" ]; then
  echo "Response file not found: $RESPONSE_FILE" >&2
  echo "Fill the template, save it, then re-run this script." >&2
  exit 2
fi

echo "==> Assessing responses from: $RESPONSE_FILE"
set +e
miv prompt assess \
  --expected-identity chatgpt \
  --pack-mode quick \
  --model gpt-4o-mini \
  --response-file "$RESPONSE_FILE" \
  --format json \
  --save "$REPORT_FILE"
ASSESS_EXIT=$?
set -e
echo "Prompt assess exit code: $ASSESS_EXIT"

if [ -f "$REPORT_FILE" ]; then
  if grep -E "sk-proj-[a-zA-Z0-9]{20,}|Bearer sk-|OPENAI_API_KEY=[^[:space:]]+" "$REPORT_FILE" 2>/dev/null; then
    echo "SECRET SCAN: LEAKED"
  else
    echo "SECRET SCAN: clean"
  fi

  python3 - <<'PY'
import json
from pathlib import Path

path = Path(".miv/reports/openai-v013-prompt-smoke.json")
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

  git check-ignore -v "$REPORT_FILE" || true
fi

echo
echo "NOTE: manual_mode=true — acceptable for local validation, not for live tag gate."
exit "$ASSESS_EXIT"
