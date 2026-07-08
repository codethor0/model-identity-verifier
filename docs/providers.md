# Providers

## Verification modes

### API mode (`miv verify`)

Calls the provider API using user-supplied credentials. Inspects responses and any metadata the provider exposes.

### Manual prompt mode (`miv prompt`)

Does not call providers. Users copy generated prompts into an LLM interface and paste responses back for analysis. See [manual-mode.md](manual-mode.md).

## Supported providers

| Name | API | Env key |
| --- | --- | --- |
| mock | Local mock (no network) | (none) |
| openai | OpenAI Chat Completions | OPENAI_API_KEY |
| anthropic | Anthropic Messages | ANTHROPIC_API_KEY |
| deepseek | DeepSeek OpenAI-compatible | DEEPSEEK_API_KEY |
| gemini | Google Generative Language | GOOGLE_API_KEY |
| openrouter | OpenRouter OpenAI-compatible | OPENROUTER_API_KEY |

## API key safety

- Environment variables are recommended.
- CLI `--api-key` is supported but less safe (may appear in shell history).
- Keys are redacted from errors and stored metadata.

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
- Match type: exact, alias, mismatch, missing, or opaque

Router metadata is heuristic unless explicit fields are supplied. Opaque routing without metadata produces warnings, not proof of misrouting.

## Metadata availability

Provider metadata availability varies by API and model. Missing metadata is reported as `route.metadata_missing`, not as a confirmed mismatch.

## Error handling

Missing API keys produce a clear error message without exposing key values.
Provider HTTP errors are caught and reported with secrets redacted.
