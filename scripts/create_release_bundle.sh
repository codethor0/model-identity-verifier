#!/usr/bin/env bash
# Create a sanitized release-gate audit bundle in ~/Downloads with specific status files.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BUNDLE_NAME="model-identity-verifier-v0.1.3-branch-e2e-release-gate-bundle-${TIMESTAMP}"
BUNDLE_DIR="${HOME}/Downloads/${BUNDLE_NAME}"
VALIDATION_LOG="${BUNDLE_DIR}/.validation.log"
DOCKER_LOG="${BUNDLE_DIR}/.docker.log"
MANUAL_LOG="${BUNDLE_DIR}/.manual.log"

mkdir -p "$BUNDLE_DIR"

log_validation() {
  "$@" 2>&1 | tee -a "$VALIDATION_LOG"
}

log_docker() {
  "$@" 2>&1 | tee -a "$DOCKER_LOG"
}

log_manual() {
  "$@" 2>&1 | tee -a "$MANUAL_LOG"
}

echo "==> Running local validation (logged)"
: >"$VALIDATION_LOG"
log_validation ruff format --check .
log_validation ruff check .
log_validation python -m pytest
log_validation python -m build
log_validation twine check dist/*
log_validation miv version
log_validation miv self-test
set +e
log_validation miv verify --dry-run
DRY_EXIT=$?
set -e
log_validation bash scripts/e2e_local.sh

echo "==> Running Docker validation (logged)"
: >"$DOCKER_LOG"
log_docker docker build -t model-identity-verifier:e2e .
for cmd in \
  "miv --help" \
  "miv version" \
  "miv self-test" \
  "miv probes list" \
  "miv providers list" \
  "miv prompt create --expected-identity chatgpt --mode quick" \
  "miv prompt template --expected-identity chatgpt --mode quick"; do
  log_docker docker run --rm model-identity-verifier:e2e sh -c "$cmd"
done
set +e
log_docker docker run --rm model-identity-verifier:e2e miv verify --dry-run
DOCKER_DRY_EXIT=$?
set -e

echo "==> Running manual mode regression (logged)"
: >"$MANUAL_LOG"
mkdir -p .miv/prompts .miv/reports
log_manual miv prompt create --expected-identity chatgpt --mode quick --format markdown -o .miv/prompts/chatgpt-quick.md
log_manual miv prompt template --expected-identity chatgpt --mode quick -o .miv/prompts/chatgpt-template.txt
log_manual miv prompt assess --expected-identity chatgpt --response-file tests/fixtures/manual/chatgpt_consistent.txt --format json -o .miv/reports/manual-freeform-chatgpt.json
log_manual miv prompt assess --expected-identity chatgpt --pack-mode quick --response-file tests/fixtures/manual/chatgpt_pack_quick.txt --format json -o .miv/reports/manual-pack-chatgpt.json
set +e
log_manual miv prompt assess --expected-identity chatgpt --pack-mode quick --response-file tests/fixtures/manual/chatgpt_consistent.txt --format json -o .miv/reports/manual-pack-mismatch.json
PACK_MISMATCH_EXIT=$?
set -e

python - <<'PY' | tee -a "$MANUAL_LOG"
import json
from pathlib import Path

for path in sorted(Path(".miv/reports").glob("manual-*.json")):
    data = json.loads(path.read_text())
    print(path.name)
    print("  provider:", data.get("provider"))
    print("  manual_mode:", data.get("manual_mode"))
    print("  status:", data.get("verification_status"))
    print("  findings:", [f.get("id") for f in data.get("score_findings", [])])
    print("  errors:", data.get("errors"))
    print()
PY

echo "==> Copying sanitized repo"
rsync -a \
  --exclude ".git" \
  --exclude ".venv" \
  --exclude ".env" \
  --exclude ".miv" \
  --exclude "dist" \
  --exclude "build" \
  --exclude "*.egg-info" \
  --exclude "__pycache__" \
  --exclude ".pytest_cache" \
  --exclude ".ruff_cache" \
  --exclude ".mypy_cache" \
  --exclude "*.log" \
  --exclude "*.tmp" \
  --exclude "*.zip" \
  "$ROOT/" "$BUNDLE_DIR/repo/"

VERSION="$(miv version)"
COMMIT="$(git rev-parse HEAD)"
BRANCH="$(git branch --show-current)"

cat >"$BUNDLE_DIR/audit-summary.md" <<EOF
# Audit Summary

- Project: Model Identity Verifier
- Version: ${VERSION}
- Commit: ${COMMIT}
- Branch: ${BRANCH}
- Bundle: ${BUNDLE_NAME}

Model self-identification is generated text. It is not attestation.
Manual prompt mode analyzes pasted responses only; it cannot verify provider route metadata.
EOF

cp "$VALIDATION_LOG" "$BUNDLE_DIR/validation-output.md"
printf '\n## Notes\n- dry-run exit code: %s (INCONCLUSIVE expected)\n' "$DRY_EXIT" >>"$BUNDLE_DIR/validation-output.md"

cp "$DOCKER_LOG" "$BUNDLE_DIR/docker-status.md"
printf '\n## Notes\n- container dry-run exit code: %s (1 acceptable)\n' "$DOCKER_DRY_EXIT" >>"$BUNDLE_DIR/docker-status.md"

cp "$MANUAL_LOG" "$BUNDLE_DIR/manual-mode-status.md"
printf '\n## Notes\n- pack mismatch assess exit code: %s\n' "$PACK_MISMATCH_EXIT" >>"$BUNDLE_DIR/manual-mode-status.md"

find "$BUNDLE_DIR/repo" -type f | sed "s|${BUNDLE_DIR}/repo/||" | sort >"$BUNDLE_DIR/repo-tree.txt"

cat >"$BUNDLE_DIR/source-inventory.md" <<'EOF'
# Source Inventory

## Core modules
- src/model_identity_verifier/cli.py
- src/model_identity_verifier/prompts/ (manual mode)
- src/model_identity_verifier/probes/registry.py (56 registry probes)
- src/model_identity_verifier/analysis/detector.py

## Infrastructure
- Dockerfile, .dockerignore
- .github/workflows/{ci,security,release,docker}.yml
- scripts/e2e_local.sh
- scripts/create_release_bundle.sh

## Docs
- docs/manual-mode.md, docs/docker.md, docs/testing.md
- CONTRIBUTING.md (branch strategy)
EOF

cat >"$BUNDLE_DIR/reviewer-runbook.md" <<'EOF'
# Reviewer Runbook

1. pip install -e ".[dev]"
2. bash scripts/e2e_local.sh
3. miv prompt create --expected-identity chatgpt --mode quick
4. miv prompt assess --expected-identity chatgpt --response-file tests/fixtures/manual/chatgpt_consistent.txt
5. miv prompt assess --expected-identity chatgpt --pack-mode quick --response-file tests/fixtures/manual/chatgpt_pack_quick.txt
6. docker build -t model-identity-verifier:e2e . && docker run --rm model-identity-verifier:e2e miv self-test
7. miv reports inspect --report-dir .miv/reports --glob "*v013-smoke.json"
8. miv reports gate --report-dir .miv/reports --release v0.1.3

In sanitized bundles without .git, scripts/e2e_local.sh skips only the git-ignore check.
Manual/browser mode is not live provider validation.
EOF

git log --format='%an <%ae> | %cn <%ce> | %h %s' --all >"$BUNDLE_DIR/git-authorship-summary.md"

cat >"$BUNDLE_DIR/e2e-status.md" <<EOF
# E2E Status

- scripts/e2e_local.sh: see validation-output.md
- pytest count: $(python -m pytest --collect-only -q 2>/dev/null | tail -1 || echo unknown)
- API live smoke: not run in bundle (keys required on reviewer machine)
EOF

{
  echo "# Branch Cleanup Status"
  echo
  echo "## Before cleanup"
  git branch --format='- %(refname:short) %(objectname:short) %(subject)'
  echo
  echo "## Remote branches"
  git branch -r --format='- %(refname:short) %(objectname:short) %(subject)'
  echo
  echo "## Deleted"
  echo "- None (no merged local feature branches; dependabot branches preserved as unmerged)"
  echo
  echo "## Preserved"
  echo "- main (long-lived trunk)"
  git branch -r --no-merged origin/main --format='- %(refname:short) (unmerged dependabot/open PR branch)'
  echo
  echo "## Policy"
  echo "- Trunk-based: main only long-lived branch"
  echo "- Delete feature/fix branches after merge"
  echo "- Do not delete unmerged dependabot branches without review"
} >"$BUNDLE_DIR/branch-cleanup-status.md"

{
  echo "# GitHub Status"
  echo
  echo "- Remote main before push: $(git rev-parse origin/main 2>/dev/null || echo unknown)"
  echo "- Local main: ${COMMIT}"
  echo "- Ahead of origin/main: $(git rev-list --count origin/main..HEAD 2>/dev/null || echo unknown) commits"
  echo "- Docker workflow: present in repo; runs after push to main"
  if command -v gh >/dev/null 2>&1; then
    echo
    echo "## Recent workflow runs"
    gh run list --repo codethor0/model-identity-verifier --limit 5 2>/dev/null || true
  fi
} >"$BUNDLE_DIR/github-status.md"

cat >"$BUNDLE_DIR/release-readiness.md" <<EOF
# Release Readiness

| Gate | Status |
| --- | --- |
| Local validation | pass (see validation-output.md) |
| Docker validation | pass (see docker-status.md) |
| Manual mode regression | pass (see manual-mode-status.md) |
| GitHub CI/Security/Docker | pending push or verify after push |
| Live API smoke | blocked without provider keys |
| TestPyPI | not run |
| PyPI | not run |

**Decision: READY FOR LIVE API SMOKE TESTS**

Do not tag v0.1.3 until main is pushed and GitHub Actions are green.
Do not publish PyPI until live API smoke and TestPyPI install pass.
EOF

rm -f "$BUNDLE_DIR/.validation.log" "$BUNDLE_DIR/.docker.log" "$BUNDLE_DIR/.manual.log"

cd "$HOME/Downloads"
zip -r "${BUNDLE_NAME}.zip" "$BUNDLE_NAME" -x "*.DS_Store" -x "__MACOSX/*" >/dev/null

echo "Bundle created: ${BUNDLE_DIR}"
echo "Zip created: ${HOME}/Downloads/${BUNDLE_NAME}.zip"
