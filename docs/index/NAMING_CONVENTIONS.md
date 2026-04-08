# 命名規範 / Naming Conventions

Last updated: 2026-04-08

本文件定義專案內的命名規則，確保新增的實驗、報告、分支在格式上保持一致。
This document defines naming rules to keep new experiments, reports, and branches consistent.

---

## Experiment 目錄

**格式**: `Experiments/R##_Description/`

| 元素 | 規則 | 範例 |
|------|------|------|
| Round 編號 | `R` + 數字，無前導零 | `R33`, `R38`, `R42` |
| 版本變體 | 加 `v2`、`v3` 後綴 | `R38v2` |
| 描述 | PascalCase，用底線分隔詞組 | `RobustLoss`, `SeqFixed`, `FreqSplit` |
| 全名 | `R##[v#]_Description` | `R33_RobustLoss`, `R38v2_SeqFixed` |

**歷史例外**（保持原名，不重新命名）：
- `R26NewPSFCheck`（無底線，PascalCase 連寫）
- `R32Sandbox`（無底線）
- `R33RobustLoss`、`R33ContrastFix`（無底線，已定案）
- `R38SeqConsistency`、`R38v2SeqFixed`（無底線，已定案）

新實驗從下一輪起使用底線格式：`R39_Description`。

## Experiment 子目錄結構

**標準結構**（必備 + 選用）：
```
R##_Description/
├── README.md          # [必備] 假說、設計、結果摘要
├── scripts/           # [建議] 訓練啟動器
│   └── launch_r##.py
├── reports/           # [必備] 結果報告、分析、方法論
│   └── R##_RESULTS.md
└── results/           # [必備] 數據產出
    ├── external_gmf/  # GMF 原始評分（如果送了外部驗證）
    ├── sequence_analysis/  # 內部 sequence analysis
    └── *_recon/       # 重建影像
```

詳見 `EXPERIMENT_TEMPLATE.md`。

## 報告檔名

**格式**: `R##_TYPE.md` 或 `TOPIC_TYPE.md`

| TYPE | 用途 | 範例 |
|------|------|------|
| RESULTS | 完整實驗結果 | `R38v2_RESULTS.md` |
| SUMMARY | 實驗摘要（含多候選） | `R33_EXPERIMENT_SUMMARY.md` |
| AUDIT | 審計/盤查報告 | `DATA_FLOW_AUDIT.md` |
| METHODOLOGY | 方法論說明 | `GMF_STEP_STD_METHODOLOGY.md` |
| ANALYSIS | 深度分析 | `INTERNAL_EXTERNAL_DIVERGENCE_ANALYSIS.md` |

- 全部大寫（`RESULTS`），底線分隔
- Round 前綴用 `R##`（不用 `ROUND##`）
- 跨 Round 的報告用範圍：`R33_R38v2_COMPLETE_EXPERIMENT_SERIES.md`
- 不用時間戳命名（Git history 提供時間資訊）

**歷史例外**：`r33_robust_p90_results.md`（小寫，已定案不改）

## Git Branch

**格式**: `sandbox/r##` 或 `sandbox/r##-description`

| 用途 | 格式 | 範例 |
|------|------|------|
| 實驗 sandbox | `sandbox/r##` | `sandbox/r33`, `sandbox/r38v2` |
| 變體 | `sandbox/r##-description` | `sandbox/r33-contrast` |
| AI agent | `codex/*` | 合併後刪除 |
| Baseline | `baseline/*` | 永久保留 |
| 研究 | `research/*` | 永久保留 |

詳見 `REPO_GOVERNANCE.md` Branch Taxonomy。

## 檔案命名通則

- Markdown：`UPPER_SNAKE_CASE.md`（報告）或 `lower_snake_case.md`（README 等）
- Python：`lower_snake_case.py`（除 Model/ 以外，Model/ 用 PascalCase 前綴）
- JSON：`lower_snake_case.json` 或 `UPPER_SNAKE_CASE.json`（政策文件）
- 不在檔名中使用中文字元（目錄名可以，檔名不要）
