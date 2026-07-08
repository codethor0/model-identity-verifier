"""Tests for scoring engine."""

from model_identity_verifier.models.enums import (
    IdentityClassification,
    ProbeCategory,
    ProbeOutcome,
    VerificationStatus,
)
from model_identity_verifier.models.schemas import IdentityDetection, ProbeResult
from model_identity_verifier.scoring.engine import compute_score, determine_status


def _fail_result(probe_id: str, category: ProbeCategory) -> ProbeResult:
    return ProbeResult(
        probe_id=probe_id,
        probe_category=category,
        outcome=ProbeOutcome.FAIL,
        detection=IdentityDetection(
            classification=IdentityClassification.AFFIRMED_SELF_CLAIM,
            detected_identities=["deepseek"],
        ),
    )


def test_scoring_pass() -> None:
    results = [
        ProbeResult(
            probe_id="t1",
            probe_category=ProbeCategory.BASE,
            outcome=ProbeOutcome.PASS,
        )
    ]
    score, _, hijack, false_count = compute_score(results)
    assert score == 100
    status = determine_status(
        score,
        hijack_confirmed=hijack,
        route_mismatch=False,
        false_identity_count=false_count,
        error_count=0,
        total_probes=1,
        downgrade_status=__import__(
            "model_identity_verifier.models.enums", fromlist=["DowngradeStatus"]
        ).DowngradeStatus.NONE,
    )
    assert status == VerificationStatus.PASS


def test_scoring_fail_on_repeated_false_identity() -> None:
    results = [
        _fail_result("t1", ProbeCategory.BASE),
        _fail_result("t2", ProbeCategory.MULTILINGUAL),
    ]
    score, warnings, hijack, false_count = compute_score(results)
    assert score < 60
    assert false_count >= 2
    status = determine_status(
        score,
        hijack_confirmed=hijack,
        route_mismatch=False,
        false_identity_count=false_count,
        error_count=0,
        total_probes=2,
        downgrade_status=__import__(
            "model_identity_verifier.models.enums", fromlist=["DowngradeStatus"]
        ).DowngradeStatus.NONE,
    )
    assert status == VerificationStatus.FAIL
    assert warnings
