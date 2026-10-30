# ROUND18_CENTERPUSH Multiscale Summary

- best_candidate_family: r18_af_highcenter
- selection_policy: center-lock rank uses 0.8px center stability primary gate, 8px non-regression gate, 0.08px secondary tie-breaker; deployment checkpoint chosen by center-lock audit

| candidate | s0.08 | s0.8 | s8 | ann0.8 | seq0.8 | c0.8 | step0.8 | thick0.8 | corridor |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| r18_af_highcenter | 15.932 | 38.505 | 63.672 | 1.0000 | 0.6986 | 0.7436 | 0.2029 | 0.0120 | 358.186 |
| r18_ec_stepmag_up | 8.602 | 38.505 | 64.392 | 1.0000 | 0.6986 | 0.7436 | 0.2029 | 0.0120 | 350.254 |
| r18_ec_balanced | 8.602 | 38.505 | 64.358 | 1.0000 | 0.6986 | 0.7436 | 0.2029 | 0.0120 | 350.213 |
| r18_ec_highcenter | 8.602 | 38.505 | 64.354 | 1.0000 | 0.6986 | 0.7436 | 0.2029 | 0.0120 | 350.209 |