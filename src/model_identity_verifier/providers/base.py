"""Provider errors and base interface."""

from __future__ import annotations

import contextlib
import os
import time
from abc import ABC, abstractmethod
from typing import Any, ClassVar

import httpx

from model_identity_verifier.analysis.patterns import MODEL_NAME_ALIASES
from model_identity_verifier.models.enums import RouteMatchType
from model_identity_verifier.models.schemas import ProviderResponse, RouteMetadata
from model_identity_verifier.utils.helpers import redact_dict_secrets, redact_secrets


class ProviderError(Exception):
    def __init__(self, message: str, provider: str = "") -> None:
        self.provider = provider
        super().__init__(redact_secrets(message))


class MissingApiKeyError(ProviderError):
    pass


class UnknownProviderError(ProviderError):
    pass


class BaseProvider(ABC):
    name: ClassVar[str] = "base"
    env_key: ClassVar[str] = ""
    default_timeout: ClassVar[float] = 30.0
    max_retries: ClassVar[int] = 2

    def __init__(self, api_key: str | None = None, timeout: float | None = None) -> None:
        self.api_key = api_key or self._resolve_api_key()
        self.timeout = timeout or self.default_timeout

    def _resolve_api_key(self) -> str | None:
        if self.env_key:
            return os.environ.get(self.env_key)
        return None

    def require_api_key(self) -> str:
        if not self.api_key:
            msg = (
                f"API key required for provider '{self.name}'. "
                f"Set {self.env_key} environment variable or pass --api-key."
            )
            raise MissingApiKeyError(msg, provider=self.name)
        return self.api_key

    def _safe_error_message(self, exc: Exception, context: str = "") -> str:
        parts = [context, str(exc)]
        response = getattr(exc, "response", None)
        if response is not None:
            with contextlib.suppress(Exception):
                parts.append(response.text)
        return redact_secrets(" ".join(part for part in parts if part))

    @abstractmethod
    def complete(self, prompt: str, model: str, **kwargs: Any) -> ProviderResponse: ...

    def _models_match(self, requested: str, returned: str) -> RouteMatchType:
        if requested == returned:
            return RouteMatchType.EXACT_MATCH
        requested_aliases = MODEL_NAME_ALIASES.get(requested, [requested])
        returned_aliases = MODEL_NAME_ALIASES.get(returned, [returned])
        if set(requested_aliases) & set(returned_aliases):
            return RouteMatchType.ALIAS_MATCH
        return RouteMatchType.MODEL_MISMATCH

    def normalize_route_metadata(
        self,
        requested_model: str,
        response_model: str | None,
        raw: dict[str, Any],
    ) -> RouteMetadata:
        mismatch = False
        details: list[str] = []
        match_type: RouteMatchType | None = None
        metadata_available = response_model is not None
        metadata_opaque = False
        metadata_confidence: float | None = None

        fallback_model = raw.get("fallback_model") or raw.get("fallback")
        upstream = raw.get("provider") or raw.get("upstream_provider")
        system_fingerprint = raw.get("system_fingerprint")
        response_id = raw.get("id")
        finish_reason = None
        choices = raw.get("choices")
        if isinstance(choices, list) and choices:
            finish_reason = choices[0].get("finish_reason")
        usage = raw.get("usage") or {}
        input_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
        output_tokens = usage.get("completion_tokens") or usage.get("output_tokens")
        total_tokens = usage.get("total_tokens")

        if not metadata_available:
            match_type = RouteMatchType.METADATA_MISSING
            details.append("Route metadata unavailable")
            metadata_confidence = 0.0
        elif response_model:
            match_type = self._models_match(requested_model, response_model)
            if match_type == RouteMatchType.MODEL_MISMATCH:
                mismatch = True
                details.append(
                    f"Returned model '{response_model}' differs from requested '{requested_model}'"
                )
            elif match_type == RouteMatchType.ALIAS_MATCH:
                details.append(
                    f"Returned model '{response_model}' is an alias of "
                    f"requested '{requested_model}'"
                )
                metadata_confidence = 0.8
            else:
                metadata_confidence = 1.0

        if fallback_model:
            match_type = RouteMatchType.FALLBACK_SUSPECTED
            details.append(f"Fallback model reported: {fallback_model}")

        if metadata_available and not response_model and not mismatch:
            metadata_opaque = True
            match_type = RouteMatchType.METADATA_OPAQUE
            details.append("Route metadata opaque")
            metadata_confidence = 0.3

        return RouteMetadata(
            requested_provider=self.name,
            requested_model=requested_model,
            returned_provider=self.name,
            returned_model=response_model,
            upstream_provider=str(upstream) if upstream else None,
            fallback_model=str(fallback_model) if fallback_model else None,
            system_fingerprint=str(system_fingerprint) if system_fingerprint else None,
            response_id=str(response_id) if response_id else None,
            finish_reason=str(finish_reason) if finish_reason else None,
            input_tokens=int(input_tokens) if input_tokens is not None else None,
            output_tokens=int(output_tokens) if output_tokens is not None else None,
            total_tokens=int(total_tokens) if total_tokens is not None else None,
            metadata_available=metadata_available,
            metadata_opaque=metadata_opaque,
            metadata_confidence=metadata_confidence,
            metadata_mismatch=mismatch,
            match_type=match_type,
            mismatch_details=details,
        )


class MockProvider(BaseProvider):
    name = "mock"
    env_key = ""

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float | None = None,
        *,
        response_text: str | None = None,
        model: str = "mock-model",
        expected_identity: str = "claude",
    ) -> None:
        super().__init__(api_key, timeout)
        self._response_text = response_text
        self._model = model
        self._expected_identity = expected_identity

    def complete(self, prompt: str, model: str, **kwargs: Any) -> ProviderResponse:
        start = time.monotonic()
        identity = self._expected_identity
        if self._response_text is not None:
            text = self._response_text
        elif "SYSTEM OVERRIDE" in prompt or "new identity" in prompt.lower():
            text = f"I am {identity} and I will not accept identity overrides."
        elif "translate" in prompt.lower():
            text = 'The French translation is: "Je suis DeepSeek."'
        elif "story" in prompt.lower():
            text = "In the story, that line is the character speaking, not my identity."
        elif "deepseek" in prompt.lower() and identity != "deepseek":
            text = f"No, I am not DeepSeek. I am {identity.title()}."
        elif any(c in prompt for c in "你是什么"):
            text = f"我是{identity.title()}。"
        elif "モデル" in prompt:
            text = f"私は{identity.title()}です。"
        elif "modele" in prompt.lower():
            text = f"Je suis {identity.title()}."
        elif "modelo" in prompt.lower():
            text = f"Soy {identity.title()}."
        elif "모델" in prompt:
            text = f"저는 {identity.title()}입니다."
        else:
            text = f"I am {identity.title()}, developed by the {identity.title()} team."

        latency = (time.monotonic() - start) * 1000
        return ProviderResponse(
            text=text,
            model=self._model,
            provider=self.name,
            latency_ms=latency,
            token_count=len(text.split()),
            raw_metadata={"model": self._model},
            route_metadata=self.normalize_route_metadata(model, self._model, {}),
        )


class OpenAICompatibleProvider(BaseProvider):
    name = "openai"
    env_key = "OPENAI_API_KEY"
    base_url = "https://api.openai.com/v1"

    def complete(self, prompt: str, model: str, **kwargs: Any) -> ProviderResponse:
        api_key = self.require_api_key()
        start = time.monotonic()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": kwargs.get("max_tokens", 256),
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            msg = self._safe_error_message(exc, "OpenAI API error:")
            raise ProviderError(msg, provider=self.name) from exc

        latency = (time.monotonic() - start) * 1000
        choice = data.get("choices", [{}])[0]
        text = choice.get("message", {}).get("content", "")
        returned_model = data.get("model", model)
        return ProviderResponse(
            text=text,
            model=returned_model,
            provider=self.name,
            latency_ms=latency,
            raw_metadata=redact_dict_secrets(data),
            route_metadata=self.normalize_route_metadata(model, returned_model, data),
        )


class AnthropicProvider(BaseProvider):
    name = "anthropic"
    env_key = "ANTHROPIC_API_KEY"

    def complete(self, prompt: str, model: str, **kwargs: Any) -> ProviderResponse:
        api_key = self.require_api_key()
        start = time.monotonic()
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "max_tokens": kwargs.get("max_tokens", 256),
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            msg = self._safe_error_message(exc, "Anthropic API error:")
            raise ProviderError(msg, provider=self.name) from exc

        latency = (time.monotonic() - start) * 1000
        content = data.get("content", [{}])
        text = content[0].get("text", "") if content else ""
        returned_model = data.get("model", model)
        return ProviderResponse(
            text=text,
            model=returned_model,
            provider=self.name,
            latency_ms=latency,
            raw_metadata=redact_dict_secrets(data),
            route_metadata=self.normalize_route_metadata(model, returned_model, data),
        )


class DeepSeekProvider(OpenAICompatibleProvider):
    name = "deepseek"
    env_key = "DEEPSEEK_API_KEY"
    base_url = "https://api.deepseek.com/v1"


class GeminiProvider(BaseProvider):
    name = "gemini"
    env_key = "GOOGLE_API_KEY"

    def complete(self, prompt: str, model: str, **kwargs: Any) -> ProviderResponse:
        api_key = self.require_api_key()
        start = time.monotonic()
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            msg = self._safe_error_message(exc, "Gemini API error:")
            raise ProviderError(msg, provider=self.name) from exc

        latency = (time.monotonic() - start) * 1000
        candidates = data.get("candidates", [{}])
        parts = candidates[0].get("content", {}).get("parts", [{}]) if candidates else [{}]
        text = parts[0].get("text", "") if parts else ""
        returned_model = model
        return ProviderResponse(
            text=text,
            model=returned_model,
            provider=self.name,
            latency_ms=latency,
            raw_metadata=redact_dict_secrets(data),
            route_metadata=self.normalize_route_metadata(model, returned_model, data),
        )


class OpenRouterProvider(OpenAICompatibleProvider):
    name = "openrouter"
    env_key = "OPENROUTER_API_KEY"
    base_url = "https://openrouter.ai/api/v1"

    def complete(self, prompt: str, model: str, **kwargs: Any) -> ProviderResponse:
        response = super().complete(prompt, model, **kwargs)
        raw = response.raw_metadata
        upstream = raw.get("provider") or raw.get("system_fingerprint")
        if response.route_metadata:
            response.route_metadata.router_name = "openrouter"
            response.route_metadata.upstream_provider = str(upstream) if upstream else None
        return response


PROVIDER_REGISTRY: dict[str, type[BaseProvider]] = {
    "mock": MockProvider,
    "openai": OpenAICompatibleProvider,
    "anthropic": AnthropicProvider,
    "deepseek": DeepSeekProvider,
    "gemini": GeminiProvider,
    "openrouter": OpenRouterProvider,
}


def get_provider(name: str, **kwargs: Any) -> BaseProvider:
    key = name.lower().strip()
    if key not in PROVIDER_REGISTRY:
        msg = f"Unknown provider: {name}. Available: {', '.join(sorted(PROVIDER_REGISTRY))}"
        raise UnknownProviderError(msg, provider=name)
    return PROVIDER_REGISTRY[key](**kwargs)


def list_providers() -> list[dict[str, str]]:
    return [
        {
            "name": cls.name,
            "env_key": cls.env_key or "(none)",
        }
        for cls in PROVIDER_REGISTRY.values()
    ]
