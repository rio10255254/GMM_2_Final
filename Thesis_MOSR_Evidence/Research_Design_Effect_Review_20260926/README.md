# MOSR 模型設計與效果回顧

這份資料夾是「設計思路與實際效果」的輕量回顧，不是第二份完整實驗備份。整理日期：2026-09-26。

## 建議閱讀順序

1. [快速導覽](00_START_HERE/README.md)
2. [跨輪總評](05_Cross_Round_Analysis/MASTER_REVIEW.md)
3. [模型設計如何演進](05_Cross_Round_Analysis/DESIGN_EVOLUTION.md)
4. [按用途排名](05_Cross_Round_Analysis/OBJECTIVE_RANKINGS.md)
5. [反覆出現的失敗模式](05_Cross_Round_Analysis/FAILURE_PATTERNS.md)
6. [我的建議](05_Cross_Round_Analysis/RECOMMENDATIONS.md)

## 資料夾

- `01_Foundations_and_Failure_Modes`：先把量測定義、反例和失敗機制釐清。
- `02_Core_Model_Line`：R128／R129到R137／R140v2的主要模型路線。
- `03_PSF_Experiment_Line`：R138到R147的PSF配對、選擇器及成像一致性實驗。
- `04_Current_Optimization`：停止的R148與目前訓練中的R148v2。
- `05_Cross_Round_Analysis`：統一比較與評論。

每一輪內先讀 `COMMENTARY.md`，再依需要打開原始 `reports/`、`architecture/` 和 `key_results/`。

## 完整原件

`SOURCE_INDEX.csv`列出每輪原始位置、檔案數和總容量。大型重建影像、權重和訓練資料沒有重複複製；需要時直接回到原實驗。`MANIFEST.json`與`MANIFEST.csv`記錄本回顧包每個複製檔的來源、大小和SHA-256。

目前R148v2仍在背景訓練；本包只保存設計、短測及建立當下的收據，不提前填入正式效果。
