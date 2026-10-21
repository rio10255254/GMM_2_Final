# R68 Results

## Outcome

- R61v16 real-FOV pilot result: **PASS**.
- Validated input coverage: 301 Raw frames and 301 matching R61 reconstructions.
- Evidence scope: external to R61v16 training; cross-magnification and cross-field within the available acquisitions.
- Universal cross-sample claim: not made until physical sample identity is confirmed and additional samples are tested.

## Sequence results

| Sequence | Raw usable | R61 valid | Direction | Motion scale | Median difference | P95 difference | Response | Result |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 5x_0p5um | 100.0% | 100.0% | 100.0% | 0.986 | 30.9 nm | 70.2 nm | 0.959 | PASS |
| 5x_1um | 100.0% | 99.6% | 100.0% | 1.006 | 34.0 nm | 113.2 nm | 0.913 | PASS |
| 20x_0p5um | 94.4% | 100.0% | 100.0% | 1.003 | 17.9 nm | 105.7 nm | 0.834 | PASS |
| 20x_1um | 95.6% | 100.0% | 100.0% | 0.995 | 18.8 nm | 161.8 nm | 0.814 | PASS |
| 50x_0p5um | 66.6% | 100.0% | 100.0% | 1.016 | 13.7 nm | 89.1 nm | 1.015 | PASS |
| 50x_1um | 72.2% | 99.9% | 100.0% | 0.994 | 18.0 nm | 165.2 nm | 1.031 | PASS |

## Interpretation

Each sequence was evaluated on 24 automatically selected content-rich regions across the full field of view. Long acquisition pauses were excluded. The model is judged against the Raw motion measured from the same region, so periodic patterns and local sample defects cannot be hidden by a single central crop.

Raw usable is fixed from the Raw images before R61 is judged. Local pairs with ambiguous Raw motion are excluded from the R61-valid denominator; this mainly affects the periodic 50x fields and prevents an ambiguous reference from being mislabeled as either model success or model failure.

All six sequences passed every pilot gate.

A pass supports R61v16 as the current cross-magnification candidate. It does not prove all future HS100MG samples will pass.
