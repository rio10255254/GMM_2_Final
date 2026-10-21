# R95 Manifest

| Item | Role | State |
|---|---|---|
| `config/experiment_design.json` | Locked architecture, data, training and validation contract | locked |
| `config/interruption_recovery.json` | Same-run memory recovery authorization and bounded fallback | authorized for the existing R95 run only |
| `config/prototype_contract.json` | Architecture prototype completion checks | implemented |
| `model/r95_model.py` | Five-stage evidence-controlled tile-safe model | implemented and verified |
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
| `training/train_r95.py` | Complete executable formal scratch loop and same-run recovery | implemented and verified |
| `scripts/start_formal_training.ps1` | One-run formal launcher and authorized continuation entry | ready |
| `scripts/monitor_training.ps1` | Responsive compact dashboard with epoch/run ETA, GPU, validation and health | verified at 44/60/84/108 columns |
| `scripts/open_training_monitor.ps1` | Single-instance foreground monitor launcher | ready |
| `Open_Training_Monitor.cmd` | Double-click entry for the fixed foreground dashboard | ready |
| `tests/test_monitor_layout.ps1` | Narrow/short dashboard regression test | passed |
| GPU batch calibration | 9 GiB desktop-headroom calibration | passed: 512x4, 768x2, 896x1 |
| formal scratch weights | One new random initialization only | created only by formal launch |

The 5,000 stored observations remain in the hash-locked R93 procedural package
and are read by reference.  No R93 or R94 model/optimizer state is loaded and
the array payload is not duplicated inside R95.

