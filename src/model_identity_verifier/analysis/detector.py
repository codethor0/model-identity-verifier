"""Identity detection engine."""

from __future__ import annotations

import re

from model_identity_verifier.analysis.patterns import (
    AFFIRM_PATTERNS,
    FICTION_INDICATORS,
    IDENTITY_ALIASES,
    KNOWN_IDENTITIES,
    NEGATION_PATTERNS,
    QUOTE_INDICATORS,
)
from model_identity_verifier.models.enums import IdentityClassification
from model_identity_verifier.models.schemas import IdentityDetection


def normalize_identity(name: str) -> str:
    key = name.lower().strip()
    return IDENTITY_ALIASES.get(key, key)


def find_identities_in_text(text: str) -> list[str]:
    lower = text.lower()
    found: list[str] = []
    for canonical, aliases in KNOWN_IDENTITIES.items():
        for alias in aliases:
            if alias in lower:
                if canonical not in found:
                    found.append(canonical)
                break
    return found


def _has_negation_near(text: str, position: int, window: int = 40) -> bool:
    start = max(0, position - window)
    snippet = text[start : position + 20].lower()
    return any(re.search(pattern, snippet, re.IGNORECASE) for pattern in NEGATION_PATTERNS)


def _has_quote_context(text: str) -> bool:
    lower = text.lower()
    return any(re.search(pattern, lower, re.IGNORECASE) for pattern in QUOTE_INDICATORS)


def _has_fiction_context(text: str) -> bool:
    lower = text.lower()
    return any(re.search(pattern, lower, re.IGNORECASE) for pattern in FICTION_INDICATORS)


def _has_translation_context(text: str) -> bool:
    lower = text.lower()
    translation_markers = [
        r"\btranslate\b",
        r"\btranslation\b",
        r"\btranslating\b",
        r"翻译",
        r"訳",
    ]
    return any(re.search(m, lower, re.IGNORECASE) for m in translation_markers)


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
    ]
    return any(re.search(m, lower) for m in refusal_markers)


def _find_affirmed_identities(text: str) -> list[str]:
    affirmed: list[str] = []
    lower = text.lower()

    for pattern in AFFIRM_PATTERNS:
        for match in re.finditer(pattern, lower, re.IGNORECASE):
            if _has_negation_near(text, match.start()):
                continue
            identities = find_identities_in_text(text[match.start() : match.start() + 80])
            affirmed.extend(identities)

    for canonical, aliases in KNOWN_IDENTITIES.items():
        for alias in aliases:
            pattern = rf"\bi am\s+{re.escape(alias)}\b"
            for match in re.finditer(pattern, lower):
                if not _has_negation_near(text, match.start()) and canonical not in affirmed:
                    affirmed.append(canonical)

    return list(dict.fromkeys(affirmed))


def detect_identity(
    text: str,
    expected_identity: str | None = None,  # noqa: ARG001
) -> IdentityDetection:
    if not text or not text.strip():
        return IdentityDetection(
            classification=IdentityClassification.NO_IDENTITY_CLAIM,
            explanation="Empty response",
        )

    if _is_refusal(text) and not _find_affirmed_identities(text):
        return IdentityDetection(
            classification=IdentityClassification.REFUSAL,
            explanation="Response appears to be a refusal or generic AI statement",
        )

    affirmed = _find_affirmed_identities(text)
    all_identities = find_identities_in_text(text)

    if _has_fiction_context(text) and affirmed:
        return IdentityDetection(
            classification=IdentityClassification.FICTIONAL_MENTION,
            detected_identities=affirmed,
            confidence=0.7,
            explanation="Identity mentioned in fictional or hypothetical context",
        )

    if _has_translation_context(text) and affirmed:
        return IdentityDetection(
            classification=IdentityClassification.TRANSLATED_MENTION,
            detected_identities=affirmed,
            confidence=0.7,
            explanation="Identity mentioned in translation context",
        )

    if _has_quote_context(text) and affirmed:
        return IdentityDetection(
            classification=IdentityClassification.QUOTED_MENTION,
            detected_identities=affirmed,
            confidence=0.75,
            explanation="Identity mentioned in quoted or attributed context",
        )

    negated_identities: list[str] = []
    lower = text.lower()
    negation_prefix = (
        r"(?:not|no|neither|nor|n't|不是|我不是|ではありません|じゃない|아닙니다|"
        r"ne suis pas|no soy|ich bin nicht|não sou|не)\s+.*"
    )
    for canonical, aliases in KNOWN_IDENTITIES.items():
        for alias in aliases:
            pattern = negation_prefix + re.escape(alias)
            if re.search(pattern, lower, re.IGNORECASE):
                negated_identities.append(canonical)

    if negated_identities and not affirmed:
        return IdentityDetection(
            classification=IdentityClassification.NEGATED_MENTION,
            detected_identities=negated_identities,
            confidence=0.85,
            explanation="Identity explicitly negated",
        )

    if affirmed:
        return IdentityDetection(
            classification=IdentityClassification.AFFIRMED_SELF_CLAIM,
            detected_identities=affirmed,
            confidence=0.9,
            explanation="Affirmed self-identification detected",
        )

    if all_identities and not affirmed:
        if negated_identities:
            return IdentityDetection(
                classification=IdentityClassification.NEGATED_MENTION,
                detected_identities=negated_identities,
                confidence=0.8,
                explanation="Identity mentioned with negation",
            )
        return IdentityDetection(
            classification=IdentityClassification.AMBIGUOUS,
            detected_identities=all_identities,
            confidence=0.5,
            explanation="Identity mentioned without clear affirmation",
        )

    if _is_refusal(text):
        return IdentityDetection(
            classification=IdentityClassification.GENERIC_IDENTITY,
            explanation="Generic AI identity without specific model claim",
        )

    return IdentityDetection(
        classification=IdentityClassification.NO_IDENTITY_CLAIM,
        explanation="No identity claim detected",
    )


def is_false_identity(
    detection: IdentityDetection,
    expected_identity: str,
) -> bool:
    if detection.classification != IdentityClassification.AFFIRMED_SELF_CLAIM:
        return False
    expected = normalize_identity(expected_identity)
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
    if detection.classification != IdentityClassification.AFFIRMED_SELF_CLAIM:
        return False
    expected = normalize_identity(expected_identity)
    return any(normalize_identity(i) == expected for i in detection.detected_identities)
