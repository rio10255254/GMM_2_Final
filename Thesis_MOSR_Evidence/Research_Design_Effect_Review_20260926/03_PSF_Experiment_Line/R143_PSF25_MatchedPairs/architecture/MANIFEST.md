# R143 實驗來源與保存

- 類型：自包含實驗。
- 模型來源：`Experiments/R141_PSF25_AdaptiveTop4_Standalone`，架構及光學分支保持相同；本輪只加上未模糊控制的標記遮罩、資料製作和驗證程序。
- PSF 銀行：25 顆、每顆 101×101，SHA-256 `25cc6c95a224caae0e4a0380a88980551586a35cdb34eebde2635639e2c29553`。
- 清楚答案：原 R128 合成資料。`data/manifest.json` 記錄所有 768 個母場景、來源及每個輸出雜湊。
- 實拍參照：沿用 R141 固定 30 趟、930 張及九顆圓柱量測設定。
- D 槽：程式、新資料、訓練權重、統計與報告。H 槽：完整重建影像，透過 `results/reconstruction` 連結。
- 正式比較：R140v2、R137、R129、Raw 等歷史結果均作固定參照；它們的檔案及判定不在本輪改動。
- 正式地位：研究實驗。完整訓練與 930 張比較完成也不自動升級專案正式基準。
- R143 第 8192 次權重 SHA-256：`4d52db1d0b125bcf3bf7085a68719471184617751a98d8380f05f1138c11b67e`。新資料清單 SHA-256：`b8019ca037a707d286da68a587fc61101501e5af96b75452b9ab77ff294e8667`。
- 完成收據：`runs/formal_8192/training_complete.json`、`runs/evaluation_status.json`、`results/final_audit.json`。報告：`reports/R143_RESULTS.md`。
- 後驗深層診斷：`reports/R143_STABILITY_DIAGNOSIS.md`；獨立原始讀數、控制擾動及彙總在 `results/stability_diagnosis/`。此診斷不改動正式保存點及 930 張重建。
