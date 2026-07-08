#!/usr/bin/env bash
# Review existing live smoke reports for v0.1.3 tag go/no-go. No API keys required.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REPORT_DIR="${ROOT}/.miv/reports"
REQUIRED=(
  openai-v013-smoke.json
  anthropic-v013-smoke.json
  openrouter-v013-smoke.json
)

failures=0

echo "==> required smoke reports"
for f in "${REQUIRED[@]}"; do
  if [ -f "${REPORT_DIR}/${f}" ]; then
    echo "    ${f}: present"
  else
    echo "    ${f}: MISSING" >&2
    failures=$((failures + 1))
  fi
done

if [ "$failures" -gt 0 ]; then
  echo "TAG GATE: hold — required smoke reports missing"
  exit 2
fi

echo "==> secret scan"
if grep -R "sk-proj-\|sk-ant-\|sk-or-\|sk-[a-zA-Z0-9]\{20,\}\|Bearer sk-\|ghp_\|github_pat_\|AIza" "$REPORT_DIR"/*v013-smoke.json 2>/dev/null; then
  echo "    FAILED: possible secret leakage" >&2
  exit 1
fi
echo "    clean"

echo "==> inspect and evaluate"
python3 - <<'PY'
import json
import sys
from pathlib import Path

root = Path(".miv/reports")
required = [
    "openai-v013-smoke.json",
    "anthropic-v013-smoke.json",
    "openrouter-v013-smoke.json",
]
block = 0
hold = 0

acceptable = {"PASS", "WARN", "INCONCLUSIVE", "DOWNGRADE_SUSPECTED"}

for name in required:
    path = root / name
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

    status = data.get("verification_status")
    if data.get("dry_run") is True:
        print(f"  BLOCK: {name} has dry_run=true", file=sys.stderr)
        block += 1
    if data.get("manual_mode") is True:
        print(f"  BLOCK: {name} has manual_mode=true", file=sys.stderr)
        block += 1
    if not data.get("schema_version"):
        print(f"  BLOCK: {name} missing schema_version", file=sys.stderr)
        block += 1
    if data.get("score_findings") is None:
        print(f"  BLOCK: {name} missing score_findings", file=sys.stderr)
        block += 1
    if status == "ERROR":
        print(f"  BLOCK: {name} verification_status=ERROR", file=sys.stderr)
        block += 1
    elif status == "ROUTE_MISMATCH":
        print(f"  BLOCK: {name} verification_status=ROUTE_MISMATCH", file=sys.stderr)
        block += 1
    elif status not in acceptable:
        print(f"  BLOCK: {name} unexpected status={status!r}", file=sys.stderr)
        block += 1

if block:
    print("TAG GATE: blocked — fix smoke failures before tagging", file=sys.stderr)
    sys.exit(1)

print("TAG GATE: proceed — smoke reports acceptable for v0.1.3 tag review")
print("Next: git tag -s v0.1.3 -m \"v0.1.3\" && git push origin v0.1.3")
PY
