#!/usr/bin/env bash
# Live provider smoke tests via Docker. Keys must be in the host shell only.
# Pass through with: export OPENAI_API_KEY=... (never write to repo files).
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

IMAGE="${MIV_DOCKER_IMAGE:-model-identity-verifier:e2e}"
REPORT_DIR="${ROOT}/.miv/reports"
failures=0
live_ran=0
live_skipped=0

run_step() {
  local label="$1"
  shift
  echo "==> $label"
  if "$@"; then
    echo "    ok"
  else
    echo "    FAILED: $label" >&2
    failures=$((failures + 1))
  fi
}

key_status() {
  python3 - <<'PY'
import os
for name in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"]:
    print(f"  {name}: {'set' if os.getenv(name) else 'missing'}")
PY
}

docker_miv() {
  docker run --rm \
    -e OPENAI_API_KEY \
    -e ANTHROPIC_API_KEY \
    -e OPENROUTER_API_KEY \
    -v "${REPORT_DIR}:/app/.miv/reports" \
    "$IMAGE" \
    "$@"
}

run_step "docker build" docker build -t "$IMAGE" .

run_step "docker miv version" docker run --rm "$IMAGE" miv version
run_step "docker miv self-test" docker run --rm "$IMAGE" miv self-test

echo "==> docker dry-run (exit 0 or 1 expected)"
set +e
docker run --rm "$IMAGE" miv verify --dry-run >/dev/null 2>&1
code=$?
set -e
if [ "$code" -eq 0 ] || [ "$code" -eq 1 ]; then
  echo "    ok (exit $code)"
else
  echo "    FAILED: dry-run unexpected exit $code" >&2
  failures=$((failures + 1))
fi

mkdir -p "$REPORT_DIR"

echo "==> clear prior v0.1.3 smoke reports"
rm -f "${REPORT_DIR}"/openai-v013-smoke.json \
  "${REPORT_DIR}"/anthropic-v013-smoke.json \
  "${REPORT_DIR}"/openrouter-v013-smoke.json

echo "==> key presence (set/missing only)"
key_status

run_live() {
  local provider="$1"
  local model="$2"
  local identity="$3"
  local outfile="$4"
  local extra_args="${5:-}"

  local key_var
  case "$provider" in
    openai) key_var="OPENAI_API_KEY" ;;
    anthropic) key_var="ANTHROPIC_API_KEY" ;;
    openrouter) key_var="OPENROUTER_API_KEY" ;;
    *) echo "    unknown provider: $provider" >&2; return 1 ;;
  esac

  if [ -z "${!key_var:-}" ]; then
    echo "==> ${provider} live smoke: skipped (${key_var} missing)"
    live_skipped=$((live_skipped + 1))
    return 0
  fi

  echo "==> ${provider} live smoke"
  set +e
  # shellcheck disable=SC2086
  docker_miv miv verify \
    --provider "$provider" \
    --model "$model" \
    --expected-identity "$identity" \
    --quick \
    --format json \
    --save "/app/.miv/reports/${outfile}" \
    $extra_args
  code=$?
  set -e
  if [ "$code" -ge 0 ] && [ "$code" -le 2 ]; then
    echo "    ok (exit $code)"
    live_ran=$((live_ran + 1))
  else
    echo "    FAILED: ${provider} unexpected exit $code" >&2
    failures=$((failures + 1))
  fi
}

run_live openai gpt-4o-mini chatgpt openai-v013-smoke.json
run_live anthropic claude-3-5-sonnet-20241022 claude anthropic-v013-smoke.json
run_live openrouter openai/gpt-4o-mini chatgpt openrouter-v013-smoke.json "--route-check"

if [ "$live_ran" -gt 0 ]; then
  echo "==> secret scan reports"
  if grep -R "sk-proj-\|sk-ant-\|sk-or-\|sk-[a-zA-Z0-9]\{20,\}\|Bearer sk-\|ghp_\|github_pat_\|AIza" "$REPORT_DIR"/*v013-smoke.json 2>/dev/null; then
    echo "    FAILED: possible secret leakage in reports" >&2
    failures=$((failures + 1))
  else
    echo "    clean"
  fi

  echo "==> inspect smoke reports"
  python3 - <<'PY'
import json
from pathlib import Path

root = Path(".miv/reports")
found = False
for path in sorted(root.glob("*v013-smoke.json")):
    found = True
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
if not found:
    print("  (no *v013-smoke.json reports)")
PY

  echo "==> smoke status gate"
  set +e
  python3 - <<'PY'
import json
import sys
from pathlib import Path

block = 0
for path in sorted(Path(".miv/reports").glob("*v013-smoke.json")):
    data = json.loads(path.read_text())
    status = data.get("verification_status")
    if status == "ERROR":
        print(f"    BLOCK: {path.name} verification_status=ERROR", file=sys.stderr)
        block += 1
    elif status == "ROUTE_MISMATCH":
        print(f"    BLOCK: {path.name} verification_status=ROUTE_MISMATCH", file=sys.stderr)
        block += 1
    elif data.get("dry_run") is True or data.get("manual_mode") is True:
        print(f"    BLOCK: {path.name} dry_run/manual_mode invalid for live smoke", file=sys.stderr)
        block += 1
sys.exit(1 if block else 0)
PY
  gate=$?
  set -e
  if [ "$gate" -ne 0 ]; then
    failures=$((failures + 1))
  else
    echo "    ok"
  fi
else
  echo "==> live smoke: none ran (keys missing)"
fi

echo "==> reports gitignore check"
for f in openai-v013-smoke.json anthropic-v013-smoke.json openrouter-v013-smoke.json; do
  if [ -f "$REPORT_DIR/$f" ]; then
    if git check-ignore -q "$REPORT_DIR/$f" 2>/dev/null; then
      echo "    $f: ignored"
    else
      echo "    FAILED: $f not ignored" >&2
      failures=$((failures + 1))
    fi
  fi
done

if [ "$failures" -eq 0 ]; then
  if [ "$live_ran" -eq 0 ]; then
    echo "Docker E2E passed; live smoke skipped ($live_skipped provider(s) — keys missing)"
    exit 2
  fi
  echo "Docker E2E live smoke passed ($live_ran provider(s))"
  exit 0
fi

echo "Docker E2E failed ($failures step(s))" >&2
exit 1
