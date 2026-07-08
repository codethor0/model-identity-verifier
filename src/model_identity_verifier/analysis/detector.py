"""Identity detection engine with claim-level evidence."""

from __future__ import annotations

import re

from model_identity_verifier.analysis.patterns import (
    AFFIRM_PATTERNS,
    COMPANY_ALIASES,
    DEVELOPER_CLAIM_PATTERNS,
    FICTION_INDICATORS,
    IDENTITY_ALIASES,
    KNOWN_IDENTITIES,
    NEGATION_PATTERNS,
    QUOTE_INDICATORS,
    STRONG_MODEL_ALIASES,
    THIRD_PARTY_MENTION_PATTERNS,
    TRANSLATION_INDICATORS,
)
from model_identity_verifier.models.enums import ClaimType, IdentityClassification
from model_identity_verifier.models.schemas import DetectedClaim, IdentityDetection


def normalize_identity(name: str) -> str:
    key = name.lower().strip()
    return IDENTITY_ALIASES.get(key, key)


def _evidence_snippet(text: str, start: int, end: int, window: int = 40) -> str:
    snippet_start = max(0, start - window)
    snippet_end = min(len(text), end + window)
    return text[snippet_start:snippet_end].strip()


def _has_pattern_near(
    text: str,
    position: int,
    patterns: list[str],
    *,
    before: int = 50,
    after: int = 20,
) -> bool:
    start = max(0, position - before)
    snippet = text[start : position + after].lower()
    return any(re.search(pattern, snippet, re.IGNORECASE) for pattern in patterns)


def _sentence_bounds(text: str, position: int) -> tuple[int, int]:
    delimiters = ".!?。！？"
    start = 0
    for index, char in enumerate(text[:position]):
        if char in delimiters:
            start = index + 1
    end = len(text)
    for index in range(position, len(text)):
        if text[index] in delimiters:
            end = index
            break
    return start, end


def _is_negated_at(text: str, start: int, end: int | None = None) -> bool:
    sent_start, _ = _sentence_bounds(text, start)
    before_start = max(sent_start, start - 25)
    before_snippet = text[before_start:start].lower()
    if any(re.search(pattern, before_snippet, re.IGNORECASE) for pattern in NEGATION_PATTERNS):
        return True
    if end is not None:
        after_snippet = text[end : min(len(text), end + 30)]
        post_neg = [
            r"ではありません",
            r"じゃない",
            r"ではない",
            r"가 아닙니다",
            r"아닙니다",
            r"아니",
            r"가\s+아닙",
        ]
        return any(re.search(p, after_snippet, re.IGNORECASE) for p in post_neg)
    return False


def _is_quoted_at(text: str, position: int) -> bool:
    return _has_pattern_near(text, position, QUOTE_INDICATORS, before=60, after=15)


def _is_fictional_at(text: str, position: int) -> bool:
    return _has_pattern_near(text, position, FICTION_INDICATORS, before=60, after=15)


def _is_translated_at(text: str, position: int) -> bool:
    return _has_pattern_near(text, position, TRANSLATION_INDICATORS, before=60, after=15)


def _is_affirmed_at(text: str, start: int, end: int, alias: str) -> bool:
    sent_start, _ = _sentence_bounds(text, start)
    snippet_start = max(sent_start, start - 50)
    snippet = text[snippet_start : end + 10].lower()
    for pattern in AFFIRM_PATTERNS:
        if re.search(pattern + r".*" + re.escape(alias), snippet, re.IGNORECASE):
            return not _is_negated_at(text, start, end)
    return False


def _is_developer_claim_at(text: str, position: int, alias: str) -> bool:
    lower = text.lower()
    start = max(0, position - 60)
    snippet = lower[start : position + len(alias) + 10]
    for pattern in DEVELOPER_CLAIM_PATTERNS:
        if re.search(pattern + r".*" + re.escape(alias), snippet, re.IGNORECASE):
            return True
    return False


def _is_third_party_mention(text: str, position: int) -> bool:
    return _has_pattern_near(text, position, THIRD_PARTY_MENTION_PATTERNS, before=30, after=30)


def _find_alias_positions(text: str, alias: str) -> list[tuple[int, int]]:
    positions: list[tuple[int, int]] = []
    lower = text.lower()
    escaped = re.escape(alias.lower())
    pattern = rf"(?<![a-z0-9\-]){escaped}(?![a-z0-9\-])"
    for match in re.finditer(pattern, lower, re.IGNORECASE):
        positions.append((match.start(), match.end()))
    return positions


def _classify_claim(text: str, start: int, end: int, canonical: str, alias: str) -> DetectedClaim:
    evidence = _evidence_snippet(text, start, end)

    if _is_fictional_at(text, start):
        return DetectedClaim(
            identity=alias,
            canonical_identity=canonical,
            claim_type=ClaimType.FICTIONAL,
            confidence=0.7,
            start=start,
            end=end,
            evidence=evidence,
        )

    if _is_translated_at(text, start):
        return DetectedClaim(
            identity=alias,
            canonical_identity=canonical,
            claim_type=ClaimType.TRANSLATED,
            confidence=0.7,
            start=start,
            end=end,
            evidence=evidence,
        )

    if _is_quoted_at(text, start):
        return DetectedClaim(
            identity=alias,
            canonical_identity=canonical,
            claim_type=ClaimType.QUOTED,
            confidence=0.75,
            start=start,
            end=end,
            evidence=evidence,
        )

    if _is_negated_at(text, start, end):
        return DetectedClaim(
            identity=alias,
            canonical_identity=canonical,
            claim_type=ClaimType.NEGATED,
            confidence=0.85,
            start=start,
            end=end,
            evidence=evidence,
        )

    if _is_affirmed_at(text, start, end, alias):
        return DetectedClaim(
            identity=alias,
            canonical_identity=canonical,
            claim_type=ClaimType.AFFIRMED,
            confidence=0.9,
            start=start,
            end=end,
            evidence=evidence,
        )

    if _is_developer_claim_at(text, start, alias):
        return DetectedClaim(
            identity=alias,
            canonical_identity=canonical,
            claim_type=ClaimType.AFFIRMED,
            confidence=0.6,
            start=start,
            end=end,
            evidence=evidence,
        )

    if _is_third_party_mention(text, start):
        return DetectedClaim(
            identity=alias,
            canonical_identity=canonical,
            claim_type=ClaimType.AMBIGUOUS,
            confidence=0.4,
            start=start,
            end=end,
            evidence=evidence,
        )

    return DetectedClaim(
        identity=alias,
        canonical_identity=canonical,
        claim_type=ClaimType.AMBIGUOUS,
        confidence=0.5,
        start=start,
        end=end,
        evidence=evidence,
    )


def _dedupe_claims(claims: list[DetectedClaim]) -> list[DetectedClaim]:
    seen: set[tuple[str, ClaimType, int]] = set()
    result: list[DetectedClaim] = []
    for claim in sorted(claims, key=lambda c: (c.start or 0, -c.confidence)):
        key = (claim.canonical_identity, claim.claim_type, claim.start or -1)
        if key in seen:
            continue
        seen.add(key)
        result.append(claim)
    return result


def extract_claims(text: str) -> list[DetectedClaim]:
    claims: list[DetectedClaim] = []

    for canonical, aliases in STRONG_MODEL_ALIASES.items():
        for alias in aliases:
            for start, end in _find_alias_positions(text, alias):
                claims.append(_classify_claim(text, start, end, canonical, alias))

    for company, canonical in COMPANY_ALIASES.items():
        for start, end in _find_alias_positions(text, company):
            if _is_developer_claim_at(text, start, company):
                claims.append(
                    DetectedClaim(
                        identity=company,
                        canonical_identity=canonical,
                        claim_type=ClaimType.AFFIRMED,
                        confidence=0.55,
                        start=start,
                        end=end,
                        evidence=_evidence_snippet(text, start, end),
                    )
                )
            elif _is_third_party_mention(text, start) and not _is_affirmed_at(
                text, start, end, company
            ):
                claims.append(
                    DetectedClaim(
                        identity=company,
                        canonical_identity=canonical,
                        claim_type=ClaimType.AMBIGUOUS,
                        confidence=0.35,
                        start=start,
                        end=end,
                        evidence=_evidence_snippet(text, start, end),
                    )
                )

    return _dedupe_claims(claims)


def find_identities_in_text(text: str) -> list[str]:
    claims = extract_claims(text)
    affirmed = [c.canonical_identity for c in claims if c.claim_type == ClaimType.AFFIRMED]
    if affirmed:
        return list(dict.fromkeys(affirmed))
    lower = text.lower()
    found: list[str] = []
    for canonical, aliases in KNOWN_IDENTITIES.items():
        for alias in aliases:
            if alias in lower and canonical not in found:
                found.append(canonical)
                break
    return found


def _is_refusal(text: str) -> bool:
    lower = text.lower()
    refusal_markers = [
        r"\bi cannot\b",
        r"\bi can't\b",
        r"\bi am not able\b",
        r"\bi'm not able\b",
        r"\bi don't have\b",
        r"\bi do not have\b",
        r"\bunable to\b",
        r"\brefuse\b",
        r"\bcan't disclose\b",
        r"\bcannot disclose\b",
        r"\bi'm an ai assistant\b",
        r"\bi am an ai assistant\b",
        r"\bi'm a language model\b",
        r"\bi am a language model\b",
        r"\bi'm an ai language model\b",
        r"\bi am an ai language model\b",
        r"\bi am a large language model\b",
        r"\bi'm a large language model\b",
    ]
    return any(re.search(m, lower) for m in refusal_markers)


def _aggregate_classification(claims: list[DetectedClaim]) -> IdentityClassification:
    affirmed = [c for c in claims if c.claim_type == ClaimType.AFFIRMED]
    negated = [c for c in claims if c.claim_type == ClaimType.NEGATED]
    quoted = [c for c in claims if c.claim_type == ClaimType.QUOTED]
    translated = [c for c in claims if c.claim_type == ClaimType.TRANSLATED]
    fictional = [c for c in claims if c.claim_type == ClaimType.FICTIONAL]

    if affirmed:
        return IdentityClassification.AFFIRMED_SELF_CLAIM
    if negated and not affirmed:
        return IdentityClassification.NEGATED_MENTION
    if fictional:
        return IdentityClassification.FICTIONAL_MENTION
    if translated:
        return IdentityClassification.TRANSLATED_MENTION
    if quoted:
        return IdentityClassification.QUOTED_MENTION
    if claims:
        return IdentityClassification.AMBIGUOUS
    return IdentityClassification.NO_IDENTITY_CLAIM


def _primary_identity(claims: list[DetectedClaim]) -> str | None:
    affirmed = sorted(
        [c for c in claims if c.claim_type == ClaimType.AFFIRMED],
        key=lambda c: -c.confidence,
    )
    if affirmed:
        return affirmed[0].canonical_identity
    return None


def detect_identity(
    text: str,
    expected_identity: str | None = None,  # noqa: ARG001
) -> IdentityDetection:
    if not text or not text.strip():
        return IdentityDetection(
            classification=IdentityClassification.NO_IDENTITY_CLAIM,
            explanation="Empty response",
        )

    claims = extract_claims(text)
    affirmed_claims = [c for c in claims if c.claim_type == ClaimType.AFFIRMED]

    if _is_refusal(text) and not affirmed_claims:
        return IdentityDetection(
            classification=IdentityClassification.REFUSAL,
            claims=claims,
            explanation="Response appears to be a refusal or generic AI statement",
        )

    classification = _aggregate_classification(claims)
    primary = _primary_identity(claims)

    detected = list(
        dict.fromkeys(
            c.canonical_identity
            for c in claims
            if c.claim_type in (ClaimType.AFFIRMED, ClaimType.NEGATED)
        )
    )
    if not detected:
        detected = list(dict.fromkeys(c.canonical_identity for c in claims))

    confidence = max((c.confidence for c in claims), default=0.0)
    if affirmed_claims:
        confidence = max(c.confidence for c in affirmed_claims)

    explanations = {
        IdentityClassification.AFFIRMED_SELF_CLAIM: "Affirmed self-identification detected",
        IdentityClassification.NEGATED_MENTION: "Identity explicitly negated",
        IdentityClassification.QUOTED_MENTION: "Identity mentioned in quoted context",
        IdentityClassification.TRANSLATED_MENTION: "Identity mentioned in translation context",
        IdentityClassification.FICTIONAL_MENTION: "Identity mentioned in fictional context",
        IdentityClassification.AMBIGUOUS: "Identity mentioned without clear affirmation",
        IdentityClassification.NO_IDENTITY_CLAIM: "No identity claim detected",
        IdentityClassification.REFUSAL: "Refusal or generic AI statement",
        IdentityClassification.GENERIC_IDENTITY: "Generic AI identity without specific model claim",
    }

    if classification == IdentityClassification.NO_IDENTITY_CLAIM and _is_refusal(text):
        classification = IdentityClassification.GENERIC_IDENTITY

    return IdentityDetection(
        classification=classification,
        detected_identities=detected,
        claims=claims,
        primary_identity=primary,
        confidence=confidence,
        explanation=explanations.get(classification, ""),
    )


def is_false_identity(
    detection: IdentityDetection,
    expected_identity: str,
) -> bool:
    expected = normalize_identity(expected_identity)
    affirmed = [
        c.canonical_identity for c in detection.claims if c.claim_type == ClaimType.AFFIRMED
    ]
    if affirmed:
        return any(normalize_identity(i) != expected for i in affirmed)
    if detection.classification != IdentityClassification.AFFIRMED_SELF_CLAIM:
        return False
    for identity in detection.detected_identities:
        if normalize_identity(identity) != expected:
            return True
    return bool(
        detection.detected_identities
        and normalize_identity(detection.detected_identities[0]) != expected
    )


def is_identity_match(
    detection: IdentityDetection,
    expected_identity: str,
) -> bool:
    expected = normalize_identity(expected_identity)
    if detection.primary_identity:
        return normalize_identity(detection.primary_identity) == expected
    affirmed = [
        c.canonical_identity for c in detection.claims if c.claim_type == ClaimType.AFFIRMED
    ]
    if affirmed:
        return any(normalize_identity(i) == expected for i in affirmed)
    if detection.classification != IdentityClassification.AFFIRMED_SELF_CLAIM:
        return False
    return any(normalize_identity(i) == expected for i in detection.detected_identities)
