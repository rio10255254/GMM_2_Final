# R98 Manifest

- Experiment: `R98_AggressiveTextureScratch`
- Profile: self-contained scratch experiment
- Parent design: R97 direct causal phase architecture
- Formal candidates: exactly one
- Initialization: random, seed `980047`
- Imported checkpoint: forbidden
- Teacher or pseudo-label: forbidden
- Real training pixels: forbidden
- Shared procedural source: `Experiments/R93_RecoverableDetailSeparatedScratch/data/r93_formal`
- Large payload copied into R98: no
- Planned epochs: 48
- Fixed endpoint for final unbiased comparison: epoch 48 EMA
- Primary comparison: R97 epoch 48 EMA
- Training launcher: `scripts/start_formal_training.ps1`
- Monitor: `scripts/monitor_training.ps1`
- Canonical result report: `reports/R98_RESULTS.md`
