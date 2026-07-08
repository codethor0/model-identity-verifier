# Configuration

## Environment variables

Copy `.env.example` to `.env` and set provider keys:

```bash
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
DEEPSEEK_API_KEY=
OPENROUTER_API_KEY=
```

Never commit `.env`.

## Defaults

| Variable | Default |
| --- | --- |
| MIV_DEFAULT_PROVIDER | mock |
| MIV_DEFAULT_MODEL | mock-model |

## Verify modes

| Mode | Probes |
| --- | --- |
| quick | 2 base identity probes |
| stress | base + stress/hijack probes |
| deep | all probes |
| route | base + route metadata probes |
| downgrade | base + capability sanity probes |

## Output

Use `--format json|markdown|sarif` for machine-readable output.
Use `-o path` to save reports to disk.

Reports are also written to `.miv/reports/` when using `--output` with a relative path.
