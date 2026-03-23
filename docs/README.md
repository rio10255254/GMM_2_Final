# Docs Navigation

這個資料夾收納 root 之外的追蹤文件，目標是讓 repository root 保持入口層，而不是變成文件堆積區。

## Layout

- `analysis/`
  - 研究路徑圖、視覺化總覽、決策路徑摘要
- `evidence/`
  - 小型、高價值、可核對的 curated experiment evidence copies
  - 進一步分成 `baseline/`、`historical_baselines/`、`falsified/`、
    `side_directions/`、`analysis/`、`runtime/`、`visuals/`
  - 另有 `EVIDENCE_MAP.md` 說明每份關鍵 evidence 支撐哪個 baseline /
    falsified line / analysis 結論
  - `visuals/README.md` 說明少量代表性 comparison sheets 的用途
- `history/`
  - 長篇完整歷史敘事與研究反省
- `index/`
  - 文件責任邊界與導航索引
- `runtime/legacy/`
  - 已追蹤的 legacy runtime / root status curated copies

## Reading Guide

1. 先看 root 的 `README.md`
2. 再看 `PROJECT_SESSION_CONTINUITY.md`
3. 需要補決策脈絡時，看 `PROJECT_CURRENT_STATE.md` 與 `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md`
4. 需要完整脈絡時，再進 `history/`

## Sync Rule

這裡只追蹤值得同步到 GitHub 的文件層輸出：

- 重大 branch 與策略脈絡
- 重要分析與決策 memo
- 小型正式證據副本
- curated legacy runtime references

不追蹤日常 runtime 噪音、即時 log spam、bulk outputs。
