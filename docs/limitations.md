# Limitations

Model self-identification is generated text. It is not attestation.

This tool cannot prove which model generated an output unless the provider exposes verifiable metadata. It detects suspicious identity behavior, route mismatch signals, and self-identification instability.

## What the tool does not do

- Prove cryptographic model identity
- Guarantee detection of all downgrades or substitutions
- Replace provider attestation or signed metadata
- Detect routing that providers do not disclose

## Downgrade detection

Downgrade detection is heuristic unless metadata proves mismatch. Statuses: NONE, SUSPECTED, LIKELY, UNKNOWN.

## Baselines

Baselines are local evidence for drift detection, not proof of identity.

## Reports

Reports may contain model responses. Review before sharing externally.
