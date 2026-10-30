# ROUND16_EDGEFIT Multiscale Summary

- best_candidate_family: r16_algfit_driftfocus
- selection_policy: center-lock rank uses 0.8px center stability primary gate, 8px non-regression gate, 0.08px secondary tie-breaker; deployment checkpoint chosen by center-lock audit

| candidate | s0.08 | s0.8 | s8 | ann0.8 | seq0.8 | c0.8 | step0.8 | thick0.8 | corridor |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| r16_algfit_driftfocus | 16.451 | 33.311 | 63.663 | 1.0000 | 0.6974 | 0.7480 | 0.2990 | 0.0119 | 228.383 |
| r16_algfit_pure | 16.291 | 33.311 | 63.671 | 1.0000 | 0.6974 | 0.7480 | 0.2990 | 0.0119 | 228.202 |
| r16_algfit_lightmono | 11.693 | 33.311 | 63.683 | 1.0000 | 0.6974 | 0.7480 | 0.2990 | 0.0119 | 222.699 |
| r16_edge_highcenter | 8.602 | 33.311 | 64.345 | 1.0000 | 0.6974 | 0.7480 | 0.2990 | 0.0119 | 219.783 |