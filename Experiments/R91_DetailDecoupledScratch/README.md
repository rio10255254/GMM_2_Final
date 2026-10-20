# R91 Detail-Decoupled Scratch

## 已核對的完成狀態（2026-10-21）

原結束摘要與完整逐輪表確認：本輪已完成60／60輪，沒有缺輪或重複；舊進度快照仍寫active，原件保留，不以它判斷目前仍在訓練。完成訓練與通過全部診斷、實體驗證或正式採用分開。

[完成與來源審查](reports/R91_PRESERVATION_AUDIT_20261021.md)／[R89到R93的設計演進](../../docs/reproducibility/scratch_lineage/README.md)。原逐筆數字、模型與資料保持原樣，本次不重新訓練或清理D。

## 原方法與歷史操作說明

下文保留原啟動前的設計與操作紀錄；修正前首頁的原始位元組見[歷史副本](../../docs/history/R91_README_BEFORE_STATUS_RECONCILIATION_20261021.md)。

R91 is one independent scratch experiment. It does not load R90, R61, V42, SEM, HS100MG, or any other model output as training material. R90 epoch 45 is only a later comparison reference.

## Purpose

- Preserve natural contours, displacement stability, and tiled reconstruction consistency.
- Recover clearer microscopic texture without using dark outlines as a shortcut.
- Train four coherent exposure observations together while keeping sensor noise independent.
- Keep all checkpoint decisions continuous and multi-axis; no single diagnostic is an automatic rejection gate.

## Folder guide

- `config`: the locked experiment design, source-isolation rules, and GPU safety policy.
- `model`: the R91 network definition.
- `training`: the directly runnable scratch trainer.
- `inference`: full-image and tiled reconstruction.
- `scripts`: dataset generation, validation, benchmark, launch, and monitoring tools.
- `data`: the 5,000-observation procedural dataset, sealed holdout, and four fixed real preview images.
- `weights`: smoke and formal checkpoints. Formal checkpoints are saved every two epochs.
- `results`: GPU benchmark plus synthetic and real live reconstructions.
- `runs`: immutable initialization evidence, progress JSON, CSV history, and the Pareto archive.

## Normal use

The formal dataset and implementation are prepared once. The full run is started with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_formal_training.ps1
```

Training status can be watched with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\monitor_training.ps1
```

The foreground monitor is a compact color-coded dashboard for live progress,
time remaining, finish ranges, GPU health, and the latest completed epoch.  It
separates patch stages and validation epochs, weights recent timings more
heavily, and switches from projected to measured stage timing once a new patch
stage has real observations.  During an active epoch it refreshes the estimated
progress bar, phase, and remaining-time range every three seconds.

The trainer intentionally has no checkpoint, resume, teacher, or pseudo-label option. A second formal launch is refused.

## Runtime policy

- 60 epochs maximum; running to epoch 60 is not itself the goal.
- Checkpoint and procedural validation every two epochs.
- Fixed 5x, 20x, and 50x real-image reconstruction at epoch 1 and every five epochs.
- Two-view and four-view batches have matched image counts.
- The measured plan leaves substantially more than 7 GiB for the desktop on the RTX A6000.

R91 is a research candidate. It does not change the formal COMBO baseline and is not an enterprise delivery model until post-training SEM, real-sequence, motion, and ONNX confirmation are complete.
