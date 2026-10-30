# 早期訓練、選模與失敗歷史

本區保存原主線訓練及早期整理批次。`Traing_Progress`是歷史固定拼字；原程式與報告仍會引用它。

2026-10-28 重整時，原本根目錄的 `Traing_Progress` 拆成兩處：`organized_*` 批次、`auto_tune_reports` 等早期整理留在這裡；每次訓練一個的 `training_progress_*` 移到 [Training_Runs](../Training_Runs/README.md)。內容與資料夾名稱都沒有改，程式與紀錄裡的路徑已跟著改到新位置。

| 研究階段 | 閱讀入口 |
|---|---|
| 最早R1至R15、原日誌與profile | [早期沿革](../../docs/reproducibility/lineage/EARLY_ROUNDS.md)、[原JSON](../../docs/reproducibility/lineage/EARLY_REPORTS.md) |
| R12至15固定模型選擇 | [多尺度方法與缺少公式](../../docs/reproducibility/legacy_multiscale/README.md) |
| organized_20260313至16、Round16至31 | [批次正式位置](../../docs/operations/LEGACY_ROUNDS_OPERATIONS.md)、[逐號表](../../docs/reproducibility/lineage/ROUND_NUMBER_MAP.md) |
| R33至COMBO主線 | [原完整系列](../R33RobustLoss/reports/R33_R38v2_COMPLETE_EXPERIMENT_SERIES.md) |
| 取回關鍵模型 | [模型用途與附件](../../docs/reproducibility/MODEL_GUIDE.md) |

`selected/reports`保留當時決策，`pending`不等於正式採用；失敗、中斷與未選模型的紀錄不能只留冠軍。舊進度`active`按當時日期閱讀，不當成現在仍有該訓練在跑。大量中途模型與生成產物不再整批補傳。
