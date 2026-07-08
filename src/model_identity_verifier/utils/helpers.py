"""Utility functions."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Any

SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"sk-ant-[a-zA-Z0-9\-]{20,}"),
    re.compile(r"AIza[a-zA-Z0-9\-_]{30,}"),
    re.compile(r"Bearer\s+[a-zA-Z0-9\-_.]+"),
    re.compile(r"api[_-]?key[\"']?\s*[:=]\s*[\"']?[a-zA-Z0-9\-_]{20,}", re.IGNORECASE),
]


def generate_session_id() -> str:
    return str(uuid.uuid4())


def compute_report_hash(data: dict[str, Any]) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def redact_secrets(text: str) -> str:
    result = text
    for pattern in SECRET_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result


def redact_dict_secrets(data: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = redact_secrets(value)
        elif isinstance(value, dict):
            result[key] = redact_dict_secrets(value)
        elif isinstance(value, list):
            result[key] = [redact_secrets(v) if isinstance(v, str) else v for v in value]
        else:
            result[key] = value
    return result
