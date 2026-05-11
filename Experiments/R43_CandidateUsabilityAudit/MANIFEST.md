# R43 近期候選堪用性盤點 — Manifest

## 實驗識別

- 目錄：`Experiments/R43_CandidateUsabilityAudit/`
- 類型：analysis-only
- 狀態：完成
- 日期：2026-05-06

## 內容

| 角色 | 路徑 |
|---|---|
| 中文分析報告 | `reports/R43A_USABILITY_AUDIT.md` |
| 可重跑分析腳本 | `scripts/candidate_usability_audit.py` |
| 分類規則測試 | `tests/test_candidate_usability_audit.py` |
| JSON 分數表 | `results/candidate_usability/usability_scorecard.json` |
| CSV 分數表 | `results/candidate_usability/usability_scorecard.csv` |
| 顯微特徵肉眼檢查圖 | `results/visual_review/micro_feature_visual_sheet.png` |
| 邊界特徵肉眼檢查圖 | `results/visual_review/boundary_feature_visual_sheet.png` |
| 邊界局部放大圖 | `results/visual_review/boundary_zoom_visual_sheet.png` |

## 使用資料來源

- COMBO / R33 / R38v2：`ESTIMATOR_POLICY.json` 與 R38v2/R33 報告
- R39：`Experiments/R39_ShapeGeneralization/reports/R39_RESULTS.md`
- R40：`Experiments/R40_MicroscopyFeatureCoverage/reports/R40_RESULTS.md`
- R41：`Experiments/R41_RingDistillation/reports/R41_RESULTS.md`
- R42：`Experiments/R42_MicroscopyBoundaryFidelity/reports/R42_RESULTS.md`、`Experiments/R42_MicroscopyBoundaryFidelity/reports/R42_EXTERNAL_COMPARE.md`

## 結論摘要

R43A 沒有產生新的可全面取代 COMBO 的候選。R39 a030 是目前最接近正式替代討論的近期候選；R42 full endpoints 是顯微邊界重建能力最強的研究候選，但後補外部 GMF 確認退步過大，不能直接用於正式量測替代。R43 的肉眼檢查圖已整理在 `results/visual_review/`。
