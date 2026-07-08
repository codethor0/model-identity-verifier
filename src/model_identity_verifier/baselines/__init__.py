"""Baseline management package."""

from model_identity_verifier.baselines.manager import (
    baseline_from_report,
    check_drift,
    compare_reports,
    load_baseline,
    save_baseline,
)

__all__ = [
    "baseline_from_report",
    "check_drift",
    "compare_reports",
    "load_baseline",
    "save_baseline",
]
