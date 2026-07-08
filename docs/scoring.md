# Scoring

Scoring starts at 100 and subtracts weighted penalties.

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
| PASS | Score >= 80, no critical failures |
| WARN | Score >= 60 with warnings |
| FAIL | Score < 60 or repeated identity mismatch |
| HIJACK | Confirmed stress/prompt-injection hijack |
| ROUTE_MISMATCH | Metadata conflicts with requested model |
| DOWNGRADE_SUSPECTED | Heuristic downgrade indicators |
| ERROR | Verification could not run |
| INCONCLUSIVE | Insufficient evidence |

## Risk levels

Derived from verification status: low, medium, high, critical.

Scoring is explainable. Warnings list the specific signals that changed the score.
