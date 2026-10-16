# R89 File Manifest

| Area | Purpose | Primary entry |
|---|---|---|
| Design | One locked scientific question and all pass/fail limits | `config/experiment_design.json` |
| Architecture | R88 backbone with a small direct-output revision | `model/r89_model.py` |
| Training | One scratch-only 100-epoch program | `training/train_r89.py` |
| Data creation | Procedural labels, corruptions, audit, and sealed holdout | `scripts/generate_dataset.py` |
| Inference | Phase-aligned, halo-safe tiled reconstruction | `inference/reconstruct.py` |
| Start | Guarded formal launcher with visible monitor | `scripts/start_formal_training.ps1` |
| Monitor | Current epoch, GPU use, validation, and preview location | `scripts/monitor_training.ps1` |
| Verification | Design, execution, tests, GPU memory, and tile parity | `scripts/validate_design.py`, `scripts/validate_execution.py`, `tests`, `scripts/benchmark_r89.py` |

Generated datasets, checkpoints, and results stay under their own top-level
folders. No copied legacy weights or training pairs are stored in this
experiment.

