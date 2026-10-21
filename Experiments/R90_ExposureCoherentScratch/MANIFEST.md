# R90 File Manifest

| Purpose | Contents |
|---|---|
| Experiment settings | `config/experiment_design.json` |
| Aggregate optical summary | `config/optical_statistics.json` |
| Frozen implementation record | `config/implementation_lock.json` |
| Architecture | `model/r90_model.py` |
| Training | `training/train_r90.py` |
| Reconstruction | `inference/reconstruct.py` |
| Data generation | `scripts/generate_dataset.py` |
| Formal start | `scripts/start_formal_training.ps1` |
| Foreground monitoring | `scripts/monitor_training.ps1` |
| Verification | `scripts/validate_design.py`, `scripts/validate_execution.py`, `scripts/benchmark_r90.py`, `tests` |
| Formal training data | `data/r90_formal` |
| Sealed independent holdout | `data/r90_locked_holdout` |
| Fixed real-image previews | `data/live_validation` |
| Checkpoints | `weights/formal` |
| Logs and progress | `runs` |
| Reconstruction previews | `results` |

## Post-run early-stop study

| Purpose | Contents |
|---|---|
| Locked candidate comparison | `config/early_stop_validation.json` |
| Frozen confirmation candidate | `config/early_stop_confirmation.json` |
| Next scratch-round design | `config/next_round_design.json` |
| Multi-stage reconstruction and appearance analysis | `scripts/run_early_stop_validation.py` |
| SEM contour, radial and trade-off analysis | `scripts/analyze_early_stop_validation.py` |
| Full 301-frame motion and tiling confirmation | `scripts/confirm_early_stop_candidate.py` |
| Correction-branch diagnosis | `scripts/diagnose_branch_tradeoffs.py` |
| ONNX export and parity checks | `scripts/export_onnx_feasibility.py`, `scripts/validate_onnx_sem_parity.py`, `scripts/summarize_onnx_sem_parity.py` |
| Early-stop comparison evidence | `results/early_stop_validation`, `reports/early_stop_validation` |
| Frozen-candidate confirmation evidence | `results/early_stop_confirmation`, `reports/early_stop_confirmation` |

The epoch-45 checkpoint is a confirmation candidate only.  It is technically
exportable, but its exposure-18 SEM contour expansion prevents it from being
treated as a universal enterprise delivery model.  COMBO remains the formal
project baseline, and the existing validated R61 ONNX package remains the
emergency delivery fallback.

Generated data and checkpoints remain inside this experiment folder. No R89
checkpoint or result is copied into R90.
