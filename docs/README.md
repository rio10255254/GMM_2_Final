# 文件導覽 / Docs Navigation

這個資料夾收納 repository root 之外、仍值得追蹤進 Git 的文件。  
This directory holds tracked documentation that lives outside the repository root.

目標是讓 root 保持成「入口層」，而不是變成文件堆積區。  
Its purpose is to keep the root as a clean entry surface instead of turning it into a document dump.

## Layout / 目錄結構

- `navigation/`
  跨區域專案地圖與查找入口；只負責指出正式位置，不複製實驗結論。
  Cross-area project map and findability entry points; it points to canonical locations without duplicating experiment verdicts.
- `analysis/`
  研究路徑圖、視覺化總覽、決策路徑摘要。
  Research-path diagrams, visual overviews, and decision-path summaries.
- `evidence/`
  小型、高價值、可核對的實驗證據副本（stable citation anchors；mirror 可能與 canonical drift，以 canonical 為準）。
  Small, high-value, reviewable curated experiment evidence copies used as stable citation anchors (mirrors may drift from canonical; canonical is authoritative).
  再細分為 `baseline/`、`historical_baselines/`、`falsified/`、`side_directions/`、`analysis/`、`runtime/`。
  Further split into `baseline/`, `historical_baselines/`, `falsified/`, `side_directions/`, `analysis/`, and `runtime/`.
  `EVIDENCE_MAP.md` 負責說明每份關鍵 evidence 支撐哪個 baseline、falsified line、或 analysis 結論。
  `EVIDENCE_MAP.md` explains which baseline, falsified line, or analytical conclusion each key evidence file supports.
- `history/`
  完整歷史敘事與研究反省（`PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md` 主體凍結於 2026-03-14，前言持續補指標）。
  Long-form historical narrative and research reflection (main body frozen at 2026-03-14, preface accumulates milestone pointers).
- `operations/`
  操作指引層：新實驗 SOP（`STARTING_NEW_EXPERIMENT.md`）、quirks（`QUIRKS.md`）、source-of-truth 政策、legacy batch 操作、控制中心說明。
  Operational guide layer: new-experiment SOP, quirks, source-of-truth policy, legacy batch operations, and the control-center guide.
- `policy/`
  正式政策文件，包含 PSF 政策切換說明與機器可讀 PSF policy。
  Formal policy documents, including the PSF policy transition rationale and machine-readable PSF policy.
- `archive/`
  封存內容。`legacy_runtime_status/` 保存 R20-R32 的 30 份 `000_LONGRUN_*_STATUS.*` 歷史快照（2026-04-08 封存）；`legacy_visuals/` 保存舊視覺比較圖。
  Archived content. `legacy_runtime_status/` holds the R20-R32 `000_LONGRUN_*_STATUS.*` history snapshots (archived 2026-04-08); `legacy_visuals/` holds retired visual comparison sheets.
- `runtime/legacy/`
  僅剩搬遷說明；實際封存已移至 `docs/archive/legacy_runtime_status/`。
  Only a relocation note remains; the real archive is now at `docs/archive/legacy_runtime_status/`.
- `superpowers/`
  本地工作文件（specs / plans），受 `.gitignore` 排除，不進 Git。
  Local working documents (specs / plans); gitignored and not committed.

## Reading Guide / 建議閱讀順序

1. 先看 root 的 `README.md`
   First read the root `README.md`.
2. 再看 `PROJECT_STATE.md`（前 50 行 Quick Handoff 區 3 分鐘讀完）
   Then read `PROJECT_STATE.md` (the first ~50 lines are the 3-minute Quick Handoff).
3. 不知道檔案在哪個工作區時，看 `navigation/PROJECT_MAP.md`
   Use `navigation/PROJECT_MAP.md` when you do not know which workspace owns something.
4. 需要穩定規則時，看 `PROJECT_ARCHITECTURE.md`
   For stable architecture rules and promotion conditions, read `PROJECT_ARCHITECTURE.md`.
5. 需要完整歷史脈絡時，再進 `history/`
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
