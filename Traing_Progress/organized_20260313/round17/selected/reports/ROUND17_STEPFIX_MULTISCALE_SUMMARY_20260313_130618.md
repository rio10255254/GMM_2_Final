# ROUND17_STEPFIX Multiscale Summary

- best_candidate_family: r17_af_stepmag
- selection_policy: center-lock rank uses 0.8px center stability primary gate, 8px non-regression gate, 0.08px secondary tie-breaker; deployment checkpoint chosen by center-lock audit

| candidate | s0.08 | s0.8 | s8 | ann0.8 | seq0.8 | c0.8 | step0.8 | thick0.8 | corridor |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| r17_af_stepmag | 15.933 | 38.504 | 63.672 | 1.0000 | 0.6995 | 0.7514 | 0.1919 | 0.0120 | 358.291 |
| r17_ec_stepmag | 8.602 | 38.504 | 64.418 | 1.0000 | 0.6995 | 0.7514 | 0.1919 | 0.0120 | 350.388 |
| r17_ec_balanced | 8.602 | 38.504 | 64.274 | 1.0000 | 0.6995 | 0.7514 | 0.1919 | 0.0120 | 350.216 |
| r17_ec_gradboost | 8.602 | 38.504 | 64.242 | 1.0000 | 0.6995 | 0.7514 | 0.1919 | 0.0120 | 350.177 |