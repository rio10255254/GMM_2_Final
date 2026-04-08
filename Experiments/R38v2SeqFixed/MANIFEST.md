# R38v2 — Sequence Consistency Training (Fixed)

| 欄位 | 值 |
|------|---|
| Round | 38v2 |
| Branch | `sandbox/r38v2` |
| Status | **External PASS** — 視覺優先型 + COMBO 最均衡型候選 |
| Mechanism | Seq 8px-only + signal gate 0.002 + warmup 15 epochs |
| External GMF 0.8px | R38v2: **0.134205** (-20%), COMBO: **0.131560** (-22%) |
| Checkpoints | R38v2: `..._20260406_235957/...`, COMBO: `..._20260408_003525/...` |
| Key Reports | `reports/R38v2_RESULTS.md`, `reports/COMBO_RESULTS.md`, `reports/DATA_FLOW_AUDIT.md` |

**此目錄包含**：R38v2（純 seq）和 COMBO（seq + Winsorize）兩個候選的結果、
量化修復版重建影像、720-angle 分析、IRLS/soft_l1 比較。
是 R38 系列的主要文件中心。

**COMBO = Winsorize p95 + R38v2 的 seq 機制**，是三個生產候選中最均衡的。

## Lineage

COMBO 同時繼承兩條線的機制：
- **R33 的 Winsorize p95**：截尾 gradient_magnitude_loss + laplacian_hf_loss
- **R38v2 的 seq training**：8px-only stages + signal gate 0.002 + warmup 15 epochs
- Launcher: `r38v2_8px_gate_p95` in `scripts/launch_r38v2.py`
- Checkpoint: `..._20260408_003525`（和 R38v2 用同一個 launcher，但多了 ROBUST_LOSS_PERCENTILE=0.95）
