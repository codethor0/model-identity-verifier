"""Provider errors and base interface."""

from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from typing import Any, ClassVar

import httpx

from model_identity_verifier.models.schemas import ProviderResponse, RouteMetadata
from model_identity_verifier.utils.helpers import redact_secrets


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

    @abstractmethod
    def complete(self, prompt: str, model: str, **kwargs: Any) -> ProviderResponse: ...

    def normalize_route_metadata(
        self,
        requested_model: str,
        response_model: str | None,
        raw: dict[str, Any],
    ) -> RouteMetadata:
        mismatch = False
        details: list[str] = []
        if response_model and response_model != requested_model:
            mismatch = True
            details.append(
                f"Requested model '{requested_model}' but metadata reports '{response_model}'"
            )
        return RouteMetadata(
            requested_provider=self.name,
            requested_model=requested_model,
            returned_provider=self.name,
            returned_model=response_model,
            metadata_available=response_model is not None,
            metadata_mismatch=mismatch,
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
            msg = f"OpenAI API error: {exc}"
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
            raw_metadata=data,
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
            msg = f"Anthropic API error: {exc}"
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
            raw_metadata=data,
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
            msg = f"Gemini API error: {exc}"
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
            raw_metadata=data,
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
