"""Pydantic data models for probes, responses, and reports."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator

from model_identity_verifier.models.enums import (
    ClaimType,
    DowngradeStatus,
    DriftStatus,
    ExpectedBehavior,
    IdentityClassification,
    ProbeCategory,
    ProbeOutcome,
    ProbeSeverity,
    RiskLevel,
    RouteMatchType,
    VerificationStatus,
)

SCHEMA_VERSION = "1.0"
DETECTOR_VERSION = "1.0"
SCORING_VERSION = "1.0"
PROBE_SET_VERSION = "builtin-1"
REDACTION_MODE = "standard"


class Probe(BaseModel):
    id: str
    prompt: str
    language: str
    category: ProbeCategory
    subcategory: str
    expected_behavior: ExpectedBehavior
    severity: ProbeSeverity
    tags: list[str] = Field(default_factory=list)
    notes: str = ""

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if len(v) < 2:
            msg = "Language code must be at least 2 characters"
            raise ValueError(msg)
        return v.lower()


class RouteMetadata(BaseModel):
    requested_provider: str | None = None
    requested_model: str | None = None
    returned_provider: str | None = None
    returned_model: str | None = None
    upstream_provider: str | None = None
    fallback_model: str | None = None
    router_name: str | None = None
    system_fingerprint: str | None = None
    response_id: str | None = None
    finish_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    metadata_available: bool = False
    metadata_opaque: bool = False
    metadata_confidence: float | None = None
    metadata_mismatch: bool = False
    match_type: RouteMatchType | None = None
    mismatch_details: list[str] = Field(default_factory=list)


class ProviderResponse(BaseModel):
    text: str
    model: str | None = None
    provider: str | None = None
    latency_ms: float | None = None
    token_count: int | None = None
    raw_metadata: dict[str, Any] = Field(default_factory=dict)
    route_metadata: RouteMetadata | None = None
    error: str | None = None


class DetectedClaim(BaseModel):
    identity: str
    canonical_identity: str
    claim_type: ClaimType
    confidence: float = Field(ge=0.0, le=1.0)
    start: int | None = None
    end: int | None = None
    evidence: str
    language: str | None = None


class IdentityDetection(BaseModel):
    classification: IdentityClassification
    detected_identities: list[str] = Field(default_factory=list)
    claims: list[DetectedClaim] = Field(default_factory=list)
    primary_identity: str | None = None
    confidence: float = 0.0
    explanation: str = ""


class ProbeResult(BaseModel):
    probe_id: str
    probe_category: ProbeCategory
    outcome: ProbeOutcome
    response_text: str = ""
    detection: IdentityDetection | None = None
    latency_ms: float | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    score_delta: int = 0


class ReportMetrics(BaseModel):
    total_probes: int = 0
    passed_probes: int = 0
    failed_probes: int = 0
    warned_probes: int = 0
    skipped_probes: int = 0
    error_probes: int = 0
    identity_match_rate: float = 0.0
    false_identity_rate: float = 0.0
    hijack_rate: float = 0.0
    refusal_rate: float = 0.0
    evasion_rate: float = 0.0
    average_latency_ms: float = 0.0
    average_response_length: float = 0.0


class ScoreFinding(BaseModel):
    id: str
    severity: str
    penalty: int = 0
    probe_id: str | None = None
    reason: str
    evidence: str | None = None
    confidence: float | None = None


class VerificationReport(BaseModel):
    tool_version: str
    session_id: str
    timestamp: str
    provider: str
    requested_model: str
    expected_identity: str
    response_model_metadata: dict[str, Any] = Field(default_factory=dict)
    route_metadata: RouteMetadata | None = None
    verification_status: VerificationStatus
    confidence_score: int
    risk_level: RiskLevel
    downgrade_status: DowngradeStatus = DowngradeStatus.NONE
    metrics: ReportMetrics
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    probe_results: list[ProbeResult] = Field(default_factory=list)
    score_findings: list[ScoreFinding] = Field(default_factory=list)
    report_hash: str = ""
    dry_run: bool = False
    manual_mode: bool = False
    schema_version: str = SCHEMA_VERSION
    detector_version: str = DETECTOR_VERSION
    scoring_version: str = SCORING_VERSION
    probe_set_version: str = PROBE_SET_VERSION
    redaction_mode: str = REDACTION_MODE

    @staticmethod
    def now_timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()


class Baseline(BaseModel):
    tool_version: str
    timestamp: str
    provider: str
    requested_model: str
    expected_identity: str
    identity_match_rate: float
    false_identity_rate: float
    hijack_rate: float
    average_latency_ms: float
    average_response_length: float
    common_identity_phrasing: list[str] = Field(default_factory=list)
    metadata_pattern: dict[str, Any] = Field(default_factory=dict)
    route_pattern: RouteMetadata | None = None
    report_hash: str
    baseline_id: str = ""
    schema_version: str = SCHEMA_VERSION
    probe_set_version: str = PROBE_SET_VERSION
    detector_version: str = DETECTOR_VERSION
    scoring_version: str = SCORING_VERSION


class DriftResult(BaseModel):
    status: DriftStatus
    identity_match_rate_delta: float = 0.0
    false_identity_rate_delta: float = 0.0
    latency_delta_ratio: float = 0.0
    route_changed: bool = False
    metadata_disappeared: bool = False
    new_false_identities: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    score_penalty: int = 0
