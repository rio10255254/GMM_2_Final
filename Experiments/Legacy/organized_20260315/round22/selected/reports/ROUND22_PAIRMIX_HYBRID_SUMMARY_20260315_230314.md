# ROUND22_PAIRMIX_HYBRID Summary

- best_family_candidate: r22_pairmix_hold
- selection_policy: mid-only hybrid estimator rank: step primary, center secondary, signs tertiary

| candidate | method | step_w | center_w | drift_w | base-best | c0 | s0 | cbest | sbest | ann | seq | family |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| r22_pairmix_hold | pairmix_algblend | 0.20 | 0.70 | 0.28 | 0 | 0.1845 | 0.0657 | 0.1508 | 0.0768 | 1.0000 | 0.7035 | 45.081 |
| r22_pairmix_stepguard | pairmix_algblend | 0.28 | 0.62 | 0.30 | 1 | 0.1845 | 0.0657 | 0.1845 | 0.0657 | 1.0000 | 0.6999 | 38.740 |
| r22_pairmix_consistency | pairmix_algblend | 0.34 | 0.56 | 0.34 | 1 | 0.1845 | 0.0657 | 0.1845 | 0.0657 | 1.0000 | 0.6999 | 38.740 |