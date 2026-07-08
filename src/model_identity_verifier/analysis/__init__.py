"""Analysis package."""

from model_identity_verifier.analysis.detector import (
    detect_identity,
    find_identities_in_text,
    is_false_identity,
    is_identity_match,
    normalize_identity,
)

__all__ = [
    "detect_identity",
    "find_identities_in_text",
    "is_false_identity",
    "is_identity_match",
    "normalize_identity",
]
