#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

failures=0

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

run_step "ruff format check" ruff format --check .
run_step "ruff lint" ruff check .
run_step "pytest" python -m pytest -q
run_step "build" python -m build
run_step "self-test" miv self-test

echo "==> dry-run (exit 1 expected)"
set +e
miv verify --dry-run >/dev/null 2>&1
code=$?
set -e
if [ "$code" -eq 0 ] || [ "$code" -eq 1 ]; then
  echo "    ok (exit $code)"
else
  echo "    FAILED: dry-run unexpected exit $code" >&2
  failures=$((failures + 1))
fi

run_step "probes list" miv probes list
run_step "providers list" miv providers list
run_step "doctor" miv doctor
run_step "prompt create" miv prompt create --expected-identity chatgpt --mode quick

mkdir -p .miv/reports
echo "==> prompt assess fixture"
set +e
miv prompt assess \
  --expected-identity chatgpt \
  --response-file tests/fixtures/manual/chatgpt_consistent.txt \
  --format json \
  -o .miv/reports/e2e-manual-fixture.json
code=$?
set -e
if [ "$code" -ge 0 ] && [ "$code" -le 2 ]; then
  echo "    ok (exit $code)"
else
  echo "    FAILED: prompt assess unexpected exit $code" >&2
  failures=$((failures + 1))
fi

echo "==> reports ignored by git"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if git check-ignore -q .miv/reports/e2e-manual-fixture.json 2>/dev/null; then
    echo "    ok"
  else
    echo "    FAILED: .miv/reports not ignored" >&2
    failures=$((failures + 1))
  fi
else
  echo "    skip: git ignore check requires a git working tree"
fi

if [ "$failures" -eq 0 ]; then
  echo "E2E local checks passed"
  exit 0
fi

echo "E2E local checks failed ($failures step(s))" >&2
exit 1
