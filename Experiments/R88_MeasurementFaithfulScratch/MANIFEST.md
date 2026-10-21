# R88 Manifest

- Experiment: `R88_MeasurementFaithfulScratch`
- Branch: `sandbox/r88-measurement-faithful-scratch`
- Status: single authorized 100-epoch scratch run active
- Active run: `R88_scratch_seed880031_20260810_205058`
- Formal baseline changed: no
- Old checkpoint, resume, teacher or pseudo-label: prohibited
- SEM, HS100MG or real-sample pixels/structures in training: none
- Model parameters: 2,361,568
- Formal scenes / observations: 1,280 / 5,120
- Train / validation / internal-test scenes: 1,024 / 128 / 128
- Locked holdout scenes / observations: 384 / 1,536
- Deployment halo: 192 px each side
- Formal run limit: one; already registered

## Locked hashes

- Formal data content: `74a9e830d377a9ca2e36a0e1b5b143ba29268a716551ff760eb8b4ecbd1d33f3`
- Locked holdout content: `b7de436a5d2589ba0e680dd4fe669d574d987119eef854bfafb6d765d04e91fe`
- Implementation lock: `69d8d6df44e59b4b3c15bb5304d8f742a7f279b774d691259e4abecfe63b890b`
- Random initial parameters: `dad4e654af62403a847a2b09f41763ba04192484b48be05caacd233bf0f7a632`

R73、R74、R87、SEM、真實顯微影像與外部 GMF 均不參與權重選擇。R88 只有在訓練完成、權重凍結並通過所有鎖定外部門檻後，才有資格討論取代既有模型。
