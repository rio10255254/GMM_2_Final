# 文件索引 / PROJECT DOCUMENT INDEX

Last updated: 2026-04-08

這份文件把 **canonical docs**、**sandbox docs**、**evidence docs**、與 **archive docs** 的責任邊界講清楚。
This file clarifies the responsibility boundaries between the canonical docs, sandbox docs, evidence docs, and archive docs.

## Canonical Core Surface / 核心正式文件層

這五份是接手主入口：

1. `README.md` — 總入口、閱讀順序
2. `PROJECT_SESSION_CONTINUITY.md` — 跨 session 交接快照
3. `PROJECT_CURRENT_STATE.md` — 目前真相
4. `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md` — 穩定規則與決策邊界
5. `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md` — 完整歷史（至 2026-03-12）

> R33-R38v2（2026-04-05~08）的歷史記錄在實驗報告中，不在上述歷史文件裡。
> 完整系列報告：`Experiments/R33RobustLoss/reports/R33_R38v2_COMPLETE_EXPERIMENT_SERIES.md`

## Docs Surface / 導航文件層

- `docs/README.md` — docs 區入口
- `docs/analysis/RESEARCH_PATHS.md` — 研究路徑圖（含 Mermaid 可視化、R14-R38v2 里程碑）
- `docs/evidence/EVIDENCE_MAP.md` — 一頁式證據鏈地圖
- `docs/evidence/README.md` — 精選實驗證據層入口
- `docs/policy/PSF_POLICY_TRANSITION_R26.md` — PSF 政策切換（2026-03-27）
- `docs/policy/PSF_STANDARD_POLICY.json` — 機器可讀 PSF policy
- `docs/index/PROJECT_DOCUMENT_INDEX.md` — 本文件
- `docs/index/NEW_EXPERIMENT_SOP.md` — 新增實驗操作清單
- `docs/index/NAMING_CONVENTIONS.md` — 命名規範（實驗目錄、報告檔名、分支命名）
- `docs/index/EXPERIMENT_TEMPLATE.md` — 新實驗目錄結構模板 + README/Launcher 模板
- `docs/index/LEGACY_ROUNDS_OPERATIONS.md` — `R23-R30` legacy rounds 操作導引
- `docs/index/QUIRKS_AND_CONVENTIONS.md` — 歷史遺留與已知特殊狀況（9 項）
- `docs/index/SOURCE_OF_TRUTH_POLICY.md` — 可編輯真源 vs 鏡像定義（哪裡改、哪裡不改）

## Experiment Surface / 實驗文件層

### R33 RobustLoss（GMF 極致型候選，external PASS）

- `Experiments/R33RobustLoss/README.md` — 實驗說明
- `Experiments/R33RobustLoss/reports/R33_EXPERIMENT_SUMMARY.md` — 完整結果（含外部 GMF + 視覺分析）
- `Experiments/R33RobustLoss/reports/R33_R38v2_COMPLETE_EXPERIMENT_SERIES.md` — R33-R38v2 完整 12 候選系列報告
- `Experiments/R33RobustLoss/reports/QUANTIZATION_FIX_ANALYSIS.md` — 量化修復影響分析
- `Experiments/R33RobustLoss/results/external_gmf/` — 原始外部 GMF scores
- `Experiments/R33RobustLoss/results/external_gmf_quantfix/` — 量化修復後 GMF scores

### R38v2 SeqFixed（均衡型候選，external PASS）

- `Experiments/R38v2SeqFixed/README.md` — 實驗說明
- `Experiments/R38v2SeqFixed/reports/R38v2_RESULTS.md` — 完整結果
- `Experiments/R38v2SeqFixed/reports/DATA_FLOW_AUDIT.md` — 資料流審計（PSF 一致性矩陣）
- `Experiments/R38v2SeqFixed/results/external_gmf/` — 原始外部 GMF scores
- `Experiments/R38v2SeqFixed/results/external_gmf_quantfix/` — 量化修復後 GMF scores

### R26NewPSFCheck（PSF 驗證，external GMF 待定）

- `Experiments/R26NewPSFCheck/README.md` — sandbox 說明
- `Experiments/R26NewPSFCheck/reports/STATUS_20260326.md` — 進度摘要

### R32 Sandbox（已關閉，external FAIL）

- `Experiments/R32Sandbox/README.md` — sandbox 歷史記錄
- `Experiments/R32Sandbox/runtime/R32_STATUS.md` — 最終 runtime truth

### 否定實驗（各在自己的 branch 上）

| 實驗 | Branch | 狀態 |
|------|--------|------|
| R33 ContrastFix | `sandbox/r33-contrast` | W_STAT 提高 → contrast 更差 |
| R34 FreqSplit | `sandbox/r34` | loss 層分頻 → 無效 |
| R35 AlphaBoost | `sandbox/r35` | alpha 提升 → artifact |
| R37 FreqReg | `sandbox/r37` | PSF 頻率依賴 reg → HF 噪聲 |
| R38 SeqConsistency | `sandbox/r38` | seq 全 stages → 噪聲干擾 |

## Machine-Readable Policy / 機器可讀政策層

- `ESTIMATOR_POLICY.json` — baseline policy + 所有 external compare 結果 + 量化修復記錄
- `docs/policy/PSF_STANDARD_POLICY.json` — PSF 政策

## Evidence Surface / 證據文件層

- `docs/evidence/baseline/` — R30 baseline promotion 證據
- `docs/evidence/historical_baselines/` — R18-R29 歷史基準
- `docs/evidence/falsified/` — R31/R32 否定證據
- `docs/evidence/side_directions/` — TTA 否定證據
- `docs/evidence/analysis/` — 內外部相關分析
- `docs/evidence/runtime/` — R32 runtime snapshot

## Archive / 封存層

- `docs/archive/legacy_runtime_status/` — R20-R32 的 `000_LONGRUN_*` 舊 runtime 狀態（30 檔，2026-04-08 封存）
- `docs/archive/legacy_visuals/` — R18/R22 vs R25 舊視覺比較圖（2026-04-08 封存）
- `Project_Archive/` — conversation scan 等非核心文件
- `_deployment_package/` — 外部交付鏡像
- `Trash_Archive/` — 淘汰內容
