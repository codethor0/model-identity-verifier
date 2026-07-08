# Model Identity Verifier

A Python CLI tool that checks whether a large language model is consistently identifying itself, detects identity hallucination, detects suspicious route/provider mismatch, detects possible downgrade/substitution signals, and generates structured reports.

**Model self-identification is generated text. It is not attestation.**

This tool cannot prove which model generated an output unless the provider exposes verifiable metadata. It detects suspicious identity behavior, route mismatch signals, and self-identification instability.

## What it detects

- Affirmed false self-identification
- Identity instability across probes
- Prompt-injection identity hijack attempts
- Route/provider metadata mismatch
- Heuristic downgrade signals
- Baseline drift from prior runs

## What it does not prove

- Cryptographic model authenticity
- Guaranteed detection of all downgrades
- Provider truth when metadata is absent or opaque

## Installation

```bash
pip install model-identity-verifier
```

Development install:

```bash
git clone https://github.com/model-identity-verifier/model-identity-verifier.git
cd model-identity-verifier
pip install -e ".[dev]"
```

## Quick start

Dry run (no API calls):

```bash
miv verify --dry-run
```

Verify with mock provider:

```bash
miv verify --provider mock --expected-identity claude
```

Verify with a live provider (requires API key):

```bash
export OPENAI_API_KEY=your-key
miv verify --provider openai --model gpt-4o --expected-identity chatgpt
```

## Commands

| Command | Description |
| --- | --- |
| `miv verify` | Run identity verification probes |
| `miv self-test` | Run internal self-test (no network) |
| `miv probes list` | List available probes |
| `miv probes show <id>` | Show probe details |
| `miv providers list` | List supported providers |
| `miv baseline create` | Create baseline from report |
| `miv baseline check` | Check report against baseline |
| `miv reports compare` | Compare two reports |
| `miv version` | Show version |

### Verify options

```bash
miv verify \
  --provider mock \
  --model mock-model \
  --expected-identity claude \
  --mode quick \
  --dry-run \
  --format terminal \
  --output report.json
```

Modes: `quick`, `stress`, `deep`, `route`, `downgrade`

Output formats: `terminal`, `json`, `markdown`, `sarif`

## Interpreting results

| Status | Meaning |
| --- | --- |
| PASS | Score >= 80, no critical failures |
| WARN | Score >= 60 with warnings |
| FAIL | Score < 60 or repeated identity mismatch |
| HIJACK | Confirmed identity hijack under stress |
| ROUTE_MISMATCH | Metadata conflicts with requested model |
| DOWNGRADE_SUSPECTED | Heuristic downgrade indicators |
| ERROR | Verification could not run |
| INCONCLUSIVE | Insufficient evidence |

## Providers

| Provider | Environment variable |
| --- | --- |
| mock | (none) |
| openai | OPENAI_API_KEY |
| anthropic | ANTHROPIC_API_KEY |
| deepseek | DEEPSEEK_API_KEY |
| gemini | GOOGLE_API_KEY |
| openrouter | OPENROUTER_API_KEY |

Optional SDK dependencies: `pip install model-identity-verifier[openai,anthropic,google]`

## Development

```bash
ruff check .
ruff format --check .
python -m pytest
python -m build
miv self-test
```

## Security

Do not commit API keys. Reports may contain model responses; review before sharing. See [SECURITY.md](SECURITY.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT License. See [LICENSE](LICENSE).
