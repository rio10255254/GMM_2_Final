# 文件導覽 / Docs Navigation

這個資料夾收納 repository root 之外、仍值得追蹤進 Git 的文件。  
This directory holds tracked documentation that lives outside the repository root.

目標是讓 root 保持成「入口層」，而不是變成文件堆積區。  
Its purpose is to keep the root as a clean entry surface instead of turning it into a document dump.

## Layout / 目錄結構

- `analysis/`
  研究路徑圖、視覺化總覽、決策路徑摘要。  
  Research-path diagrams, visual overviews, and decision-path summaries.
- `evidence/`
  小型、高價值、可核對的實驗證據副本。  
  Small, high-value, reviewable curated experiment evidence copies.
  再細分為 `baseline/`、`historical_baselines/`、`falsified/`、`side_directions/`、`analysis/`、`runtime/`、`visuals/`。  
  Further split into `baseline/`, `historical_baselines/`, `falsified/`, `side_directions/`, `analysis/`, `runtime/`, and `visuals/`.
  `EVIDENCE_MAP.md` 負責說明每份關鍵 evidence 支撐哪個 baseline、falsified line、或 analysis 結論。  
  `EVIDENCE_MAP.md` explains which baseline, falsified line, or analytical conclusion each key evidence file supports.
  `visuals/README.md` 說明少量代表性 comparison sheets 的用途。  
  `visuals/README.md` explains the purpose of the small set of representative comparison sheets.
- `history/`
  完整歷史敘事與研究反省。  
  Long-form historical narrative and research reflection.
- `index/`
  文件責任邊界、操作流程、與導航索引。  
  Documentation responsibility maps, workflow guides, and navigation indexes.
- `policy/`
  正式政策文件，包含 PSF 政策切換說明與機器可讀 PSF policy。
  Formal policy documents, including the PSF policy transition rationale and machine-readable PSF policy.
- `runtime/legacy/`
  已追蹤的 legacy runtime / root status curated copies。
  Tracked curated copies of legacy runtime and root status files.

## Reading Guide / 建議閱讀順序

1. 先看 root 的 `README.md`  
   First read the root `README.md`.
2. 再看 `PROJECT_SESSION_CONTINUITY.md`  
   Then read `PROJECT_SESSION_CONTINUITY.md`.
3. 需要補決策脈絡時，看 `PROJECT_CURRENT_STATE.md` 與 `PROJECT_ARCHITECTURE.md`  
   For decision context, read `PROJECT_CURRENT_STATE.md` and `PROJECT_ARCHITECTURE.md`.
4. 需要完整脈絡時，再進 `history/`  
   Only move into `history/` when you need the full narrative.

## Sync Rule / 同步規則

這裡只追蹤真正值得同步到 GitHub 的文件層輸出：  
This directory only tracks documentation outputs that are worth syncing to GitHub:

- 重大 branch 與策略脈絡  
  Major branches and strategy narratives
- 重要分析與決策 memo  
  Important analyses and decision memos
- 小型正式證據副本  
  Small formal evidence copies
- curated legacy runtime references  
  Curated legacy runtime references

不追蹤日常 runtime 噪音、即時 log spam、或 bulk outputs。  
It does not track day-to-day runtime noise, log spam, or bulk outputs.
