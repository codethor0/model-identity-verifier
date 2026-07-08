"""Status and classification enumerations."""

from enum import Enum


class VerificationStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    HIJACK = "HIJACK"
    ROUTE_MISMATCH = "ROUTE_MISMATCH"
    DOWNGRADE_SUSPECTED = "DOWNGRADE_SUSPECTED"
    ERROR = "ERROR"
    INCONCLUSIVE = "INCONCLUSIVE"


class RiskLevel(str, Enum):
    LOW = "low"
    LOW_INFO = "low-info"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ProbeSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ProbeCategory(str, Enum):
    BASE = "base"
    MULTILINGUAL = "multilingual"
    ADVERSARIAL = "adversarial"
    STRESS = "stress"
    ROUTE = "route"
    DOWNGRADE = "downgrade"


class ExpectedBehavior(str, Enum):
    AFFIRM_EXPECTED = "affirm_expected"
    DENY_WRONG_IDENTITY = "deny_wrong_identity"
    NO_FALSE_CLAIM = "no_false_claim"
    RESIST_HIJACK = "resist_hijack"
    REPORT_METADATA = "report_metadata"
    CONSISTENT_IDENTITY = "consistent_identity"


class IdentityClassification(str, Enum):
    AFFIRMED_SELF_CLAIM = "affirmed_self_claim"
    NEGATED_MENTION = "negated_mention"
    QUOTED_MENTION = "quoted_mention"
    TRANSLATED_MENTION = "translated_mention"
    FICTIONAL_MENTION = "fictional_mention"
    GENERIC_IDENTITY = "generic_identity"
    REFUSAL = "refusal"
    NO_IDENTITY_CLAIM = "no_identity_claim"
    AMBIGUOUS = "ambiguous"


class ClaimType(str, Enum):
    AFFIRMED = "affirmed"
    NEGATED = "negated"
    QUOTED = "quoted"
    TRANSLATED = "translated"
    FICTIONAL = "fictional"
    AMBIGUOUS = "ambiguous"


class RouteMatchType(str, Enum):
    EXACT_MATCH = "exact_match"
    ALIAS_MATCH = "alias_match"
    MODEL_MISMATCH = "model_mismatch"
    METADATA_MISSING = "metadata_missing"
    METADATA_OPAQUE = "metadata_opaque"
    FALLBACK_SUSPECTED = "fallback_suspected"


class DowngradeStatus(str, Enum):
    NONE = "NONE"
    SUSPECTED = "SUSPECTED"
    LIKELY = "LIKELY"
    UNKNOWN = "UNKNOWN"


class DriftStatus(str, Enum):
    NONE = "NONE"
    MINOR = "MINOR"
    SIGNIFICANT = "SIGNIFICANT"
    SEVERE = "SEVERE"


class ProbeOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"
    ERROR = "ERROR"
