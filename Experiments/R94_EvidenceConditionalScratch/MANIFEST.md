# R94 Manifest

| Item | Role | State |
|---|---|---|
| `config/experiment_design.json` | Locked architecture, data, training and validation contract | locked |
| `config/prototype_contract.json` | Architecture prototype completion checks | implemented |
| `model/r94_model.py` | Five-stage evidence-controlled tile-safe model | implemented and verified |
| `training/causal_stage_replay.py` | Exact hidden-stage replay and shape/material/fade decomposition | implemented and verified |
| `training/counterfactual_targets.py` | Same-scene T/P/O/B/S supervision builder | implemented and verified |
| `training/common_descent.py` | Non-opposing cross-objective update utility | implemented and verified |
| `inference/reconstruct.py` | Canonical full/tiled inference path | implemented and verified |
| `scripts/run_prototype_checks.py` | Architecture, routing, identity, translation and tiling checks | passed 17/17 |
| `scripts/validate_causal_replay.py` | Stored B-stage replay audit | passed 64/64 exactly |
| `scripts/validate_optical_layer_decomposition.py` | Causal target recomposition and crop parity | passed |
| `scripts/analyze_branch_expressivity.py` | Full validation capacity decomposition | passed 838 views |
| `scripts/analyze_oracle_targets.py` | Full target joint-improvement ceiling | passed 838 views |
| `scripts/analyze_locked_acm_ceiling.py` | Independent locked ACM target-direction check | passed 100 images |
| `scripts/validate_locked_design.py` | Fail-closed aggregate design audit | passed |
| `reports/prototype_report.json` | Generated architecture evidence | current |
| `reports/causal_replay_validation.json` | Generated stage-replay evidence | current |
| `reports/optical_layer_decomposition_validation.json` | Generated layer-label evidence | current |
| `reports/branch_expressivity_analysis.json` | Generated branch-capacity evidence | current |
| `reports/oracle_target_validation.json` | Generated joint-target ceiling | current |
| `reports/locked_acm_clean_ceiling.json` | Generated independent ACM ceiling | current |
| `reports/locked_design_audit.json` | Aggregate pass/fail audit | passed |
| formal trainer | Complete executable training loop | not implemented yet |
| GPU batch calibration | 9 GiB desktop-headroom calibration | waits for R93 GPU release |
| formal scratch weights | One new random initialization only | intentionally empty |
