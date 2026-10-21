# R129 Optical prior hybrid

Self-contained research prototype restoring the thesis's measured-optics fusion, anti-aliased upsampling and input-referenced output design. Shared R128 source data are referenced in place. Original R128/V42 models and evidence remain immutable.

The requested design requirements are retained independently of whether every metric improves. Actual module activity, matched controls and adverse measurements determine the claims; inclusion does not prove benefit or novelty.

Four matched pilot arms use one common converted decoder and original-image output anchor: A ordinary upsampling; B A plus measured optical fusion; C A plus anti-alias filter; D both. Original R128 is a separate historical reference, not mislabeled as arm A. Final intended model is D; controls are experimental only.

Branch codex/r129-optical-hybrid. Local tracking only; no external messages or publication requested. Initial budget 4 GiB. This round is a bounded integration and trainability pilot, not full retraining or production promotion.

Completed 2026-09-12: four matched 24-update pilots (96 updates), all 864 normal-SEM measurements, and four fixed real-motion pairs per method. Both major modules are active. D improves centered shape on 27/36 pillars versus the converted control, but is not an overall improvement over original R128/V42. Adaptive optical candidate selection has negligible additional effect on the checked real image. See the [actual results and limitations](reports/R129_RESULTS.md) and [comparison figure](results/figures/normal_sem_comparison.png).

One-model trial entry (Anaconda Python; PyTorch/CUDA, NumPy, SciPy, pandas and OpenCV):

```powershell
& 'C:\Users\Rio\anaconda3\python.exe' -B 'D:\GMM_2_Final\Experiments\R129_OpticalPriorHybrid\scripts\infer_image.py' --input 'C:\path\image.bmp' --output 'C:\path\new_r129.png'
```

Use 8-bit grayscale, at least 193×193 pixels; output must be a new PNG path. Default is direct full-image GPU execution. Large images need sufficient GPU memory; no tiled equivalence is claimed for the full optical stage. This entry fixes the retained D step24 checkpoint, checks its source hash and writes a provenance sidecar. It has been run on a real full SEM-paired input and reproduces the recorded image exactly.

Original failed deterministic-backward implementation and frozen plan are retained. `config/implementation_v2.json` documents the separate forward-preserving repair. Existing completed scripts intentionally refuse to overwrite evidence; inspect their outputs instead of blindly rerunning a completed run. No old model or evidence was rewritten to pass a completion check.

## Verified architecture organization

[Current architecture and module inventory](reports/R129_ARCHITECTURE.md) describes the organized implementation. `scripts/infer_organized.py` uses the same D step24 checkpoint and has been executed on a real full SEM-paired image. All eight checkpoint forward/backward checks and 11 original real-image outputs match exactly. New per-step inspection is non-mutating. The earlier `infer_image.py` remains available unchanged; this adds no training or scientific improvement claim.

## Standalone full-training follow-up

The user-requested independent package and one8192-update continuation are now running. See [package, manual controls and verified launch](reports/R129_STANDALONE_TRAINING.md). This does not replace the initial model or mean long training is complete.
