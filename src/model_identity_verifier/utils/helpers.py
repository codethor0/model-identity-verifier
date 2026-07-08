"""Utility functions."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Any
from urllib.parse import parse_qsl, urlparse, urlunparse

SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"sk-ant-api03-[a-zA-Z0-9\-]{20,}"),
    re.compile(r"sk-ant-[a-zA-Z0-9\-]{20,}"),
    re.compile(r"sk-or-[a-zA-Z0-9\-]{20,}"),
    re.compile(r"AIza[a-zA-Z0-9\-_]{30,}"),
    re.compile(r"ghp_[a-zA-Z0-9]{20,}"),
    re.compile(r"github_pat_[a-zA-Z0-9_]{20,}"),
    re.compile(r"Bearer\s+[a-zA-Z0-9\-_.]+", re.IGNORECASE),
    re.compile(r"x-api-key:\s*[a-zA-Z0-9\-_.]+", re.IGNORECASE),
    re.compile(r"Authorization:\s*Bearer\s+[a-zA-Z0-9\-_.]+", re.IGNORECASE),
    re.compile(
        r"(?:OPENAI|ANTHROPIC|GOOGLE|GEMINI|DEEPSEEK|OPENROUTER)_API_KEY"
        r"\s*[:=]\s*[\"']?[a-zA-Z0-9\-_]{8,}",
        re.IGNORECASE,
    ),
    re.compile(
        r"api[_-]?key[\"']?\s*[:=]\s*[\"']?[a-zA-Z0-9\-_]{8,}",
        re.IGNORECASE,
    ),
    re.compile(
        r"apikey[\"']?\s*[:=]\s*[\"']?[a-zA-Z0-9\-_]{8,}",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?<![a-zA-Z0-9_])(?:key|token|password)[\"']?\s*[:=]\s*[\"']?[a-zA-Z0-9\-_]{8,}",
        re.IGNORECASE,
    ),
]

_QUERY_KEY_PARAMS = frozenset({"key", "api_key", "apikey", "access_token", "token"})


def generate_session_id() -> str:
    return str(uuid.uuid4())


def compute_report_hash(data: dict[str, Any]) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _redact_url_query_params(text: str) -> str:
    def _replace_url(match: re.Match[str]) -> str:
        url = match.group(0)
        try:
            parsed = urlparse(url)
        except ValueError:
            return url
        if not parsed.query:
            return url
        new_pairs: list[str] = []
        changed = False
        for key, value in parse_qsl(parsed.query, keep_blank_values=True):
            if key.lower() in _QUERY_KEY_PARAMS and value:
                new_pairs.append(f"{key}=[REDACTED]")
                changed = True
            elif value:
                new_pairs.append(f"{key}={value}")
            else:
                new_pairs.append(key)
        if not changed:
            return url
        new_query = "&".join(new_pairs)
        return urlunparse(parsed._replace(query=new_query))

    url_pattern = re.compile(r"https?://[^\s\"']+")
    return url_pattern.sub(_replace_url, text)


def redact_secrets(text: str) -> str:
    result = _redact_url_query_params(text)
    for pattern in SECRET_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, dict):
        return redact_dict_secrets(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    return value


def redact_dict_secrets(data: dict[str, Any]) -> dict[str, Any]:
    sensitive_keys = {
        "authorization",
        "api_key",
        "apikey",
        "x-api-key",
        "token",
        "password",
        "secret",
    }
    result: dict[str, Any] = {}
    for key, value in data.items():
        if key.lower() in sensitive_keys and isinstance(value, str):
            result[key] = "[REDACTED]"
        else:
            result[key] = redact_value(value)
    return result
