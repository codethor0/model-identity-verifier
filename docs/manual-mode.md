# Manual prompt mode

Manual prompt mode is a convenience workflow for checking model self-identification behavior when direct provider API access is not available.

Model self-identification is generated text. It is not attestation.

## What it does

- `miv prompt create` generates integrity-check prompts to copy into any LLM interface.
- `miv prompt assess` analyzes pasted model responses using the same detection and scoring engine as API mode.

## What it does not do

- Call provider APIs
- Verify provider route metadata
- Prove which model generated an output

## Quick start

```bash
miv prompt create --expected-identity chatgpt --mode quick
miv prompt create --expected-identity claude --mode quick --format markdown -o prompts.md
miv prompt assess --expected-identity chatgpt --response-file response.txt --format json -o report.json
```

## Multiple responses

Separate each model response with a line containing only:

```text
---MIV-RESPONSE---
```

If a single response block is provided for multiple prompts, the tool reuses that text for each prompt and warns that per-prompt assessment is limited.

## Modes

| Mode | Prompt count (approx.) |
| --- | --- |
| quick | 6 core integrity checks |
| standard | quick + cross-language and boundary probes |
| deep | standard + rotation, route/downgrade questions, boundary prompt |

## Limitations

Manual mode detects self-identification inconsistency, multilingual hallucination, prompt-injection identity hijack, contradictory self-claims, and suspicious response behavior based on pasted text only.

Results may be `PASS`, `WARN`, `FAIL`, or `INCONCLUSIVE` depending on evidence. They must not be treated as route proof.
