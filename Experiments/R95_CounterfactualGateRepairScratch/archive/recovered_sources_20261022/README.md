# R95已找回的早期程式與設定

2026-10-22。這裡保存當時版本的完整原內容，沒有用最後版重新實作。每份均符合原執行紀錄的完整SHA-256；原修改紀錄也另存研究程式部分，沒有把私人對話或帳號資料上傳。

本輪共3版。模型定義、訓練程式、設定須按當時原紀錄配套使用，不能因為同名便互換。

| 原件 | 內容身分 | 原紀錄涉及階段 |
|---|---|---|
| [訓練程式](<810f04e36a0ecc4e6148609871f089cc4008a69ebc3e940cd6cb8672bb2f4f8a/train_r95.py>) | `810f04e36a0ecc4e6148609871f089cc4008a69ebc3e940cd6cb8672bb2f4f8a` | 預檢 20260813_002234 |
| [設定](<7431df7b46699089806f6a31e1d38e7f610bc433d5bf0dc4edff38abdaffa90d/experiment_design.json>) | `7431df7b46699089806f6a31e1d38e7f610bc433d5bf0dc4edff38abdaffa90d` | 預檢 20260813_002234；預檢 20260813_002539 |
| [訓練程式](<d0cb1a2759e5b9e26d21af29f6d0aec7d6b4daaff5a8e1c555db682d039e7c96/train_r95.py>) | `d0cb1a2759e5b9e26d21af29f6d0aec7d6b4daaff5a8e1c555db682d039e7c96` | 正式啟動 20260813_003125 |

## 如何使用這些原版

此處按內容身分存檔，是查歷史及在**新副本**重做舊階段的來源。程式內的相對位置仍按當時原資料夾設計；要操作時，應把選定版本放回新副本相應的原位置，並配對同次原模型定義、設定與固定R93資料。不要直接從archive位置啟動訓練，也不要覆寫現行工作版本。

[全部38項來源對照](<../../../../docs/reproducibility/four_rounds/HISTORICAL_SOURCE_AVAILABILITY.json>)列出每份原紀錄；[本次找回與重做限制](<../../../../docs/reproducibility/four_rounds/RECOVERY_IMPACT_20261022.md>)說明歷史中斷、更新／亂數狀態及尚未重跑的範圍。

[原來源與找回證據](<../../../../docs/reproducibility/four_rounds/SOURCE_RECOVERY_20261022.json>)／[只含相關研究程式的原修改鏈](<../../../../docs/reproducibility/four_rounds/ORIGINAL_SOURCE_PATCHES_20261022.json.gz>)。
