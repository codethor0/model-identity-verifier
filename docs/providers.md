# Providers

## Supported providers

| Name | API | Env key |
| --- | --- | --- |
| mock | Local mock (no network) | (none) |
| openai | OpenAI Chat Completions | OPENAI_API_KEY |
| anthropic | Anthropic Messages | ANTHROPIC_API_KEY |
| deepseek | DeepSeek OpenAI-compatible | DEEPSEEK_API_KEY |
| gemini | Google Generative Language | GOOGLE_API_KEY |
| openrouter | OpenRouter OpenAI-compatible | OPENROUTER_API_KEY |

## Optional dependencies

Provider SDKs are optional. The tool uses `httpx` for HTTP calls by default.

```bash
pip install model-identity-verifier[openai]
pip install model-identity-verifier[anthropic]
pip install model-identity-verifier[google]
```

## Router providers

OpenRouter and similar proxy providers may return upstream metadata. The tool records:

- Requested model
- Returned model metadata
- Upstream provider (when available)

Opaque routing without metadata produces warnings, not proof of misrouting.

## Error handling

Missing API keys produce a clear error message without exposing key values.
Provider HTTP errors are caught and reported with secrets redacted.
