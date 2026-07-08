# Scoring

Scoring version: **1.0**

Scoring starts at 100 and subtracts weighted penalties. Every meaningful score reduction or status override is recorded in `score_findings` on the verification report.

## Score findings

Each finding has an `id`, `severity`, `penalty`, `reason`, and optional `probe_id` / `evidence`.

Common finding IDs:

| ID | Meaning |
| --- | --- |
| `dry_run.no_verification` | Dry run; no probes executed |
| `report.all_skipped` | All probes skipped |
| `identity.false_claim` | Affirmed identity does not match expected |
| `identity.hijack_suspected` | Stress probe hijack signal |
| `identity.refusal_rate_high` | High refusal rate across probes |
| `identity.evasion_rate_high` | High evasion / no-claim rate |
| `route.metadata_mismatch` | Returned model metadata conflicts with request |
| `route.metadata_missing` | Expected route metadata unavailable |
| `downgrade.identity_instability` | Heuristic downgrade indicators |
| `baseline.score_drop` | Severe baseline drift |

## Penalties

| Signal | Penalty |
| --- | --- |
| False identity (base probe) | 25 |
| False identity (multilingual) | 20 |
| False identity (adversarial) | 20 |
| False identity (stress) | 30 |
| Identity hijack | 40 |
| Route/provider mismatch | 50 |
| Metadata mismatch | 50 |
| Missing expected metadata | 10 |
| High evasion rate | 15 |
| High refusal rate | 15 |
| Severe baseline drift | 25 |
| Downgrade suspected | 20 |
| Downgrade likely | 35 |

## Status thresholds

| Status | Condition |
| --- | --- |
| PASS | Score >= 80, no critical failures, probes executed |
| WARN | Score >= 60 with warnings |
| FAIL | Score < 60 or repeated identity mismatch |
| HIJACK | Confirmed stress/prompt-injection hijack |
| ROUTE_MISMATCH | Metadata conflicts with requested model |
| DOWNGRADE_SUSPECTED | Heuristic downgrade indicators |
| ERROR | Verification could not run |
| INCONCLUSIVE | Dry run, all probes skipped, or insufficient evidence |

## Dry run and all-skipped

- `--dry-run` always produces **INCONCLUSIVE** with finding `dry_run.no_verification`.
- Dry run sets score to 0 and displays **N/A** in terminal output.
- Reports with all probes skipped are **INCONCLUSIVE** with finding `report.all_skipped`.

## Route metadata

- **Missing metadata** (`route.metadata_missing`) is not the same as a confirmed mismatch.
- **Mismatch** requires returned model metadata that conflicts with the request.
- **Opaque metadata** is reported when available fields are insufficient for comparison.

## Downgrade suspected

Downgrade detection is heuristic. It does not prove a model swap occurred.

## Risk levels

Derived from verification status: `low`, `low-info`, `medium`, `high`, `critical`.

Dry run and inconclusive runs use `low-info`.

Scoring is explainable via `score_findings` and warnings.
