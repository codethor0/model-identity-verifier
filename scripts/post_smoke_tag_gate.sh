#!/usr/bin/env bash
# Review existing live smoke reports for v0.1.3 tag go/no-go. No API keys required.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate

REPORT_DIR="${ROOT}/.miv/reports"

miv reports gate --report-dir "${REPORT_DIR}" --release v0.1.3
