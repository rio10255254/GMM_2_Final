# R145 來源與執行身分

- 類型：自包含研究實驗。狀態：修正九顆圓方向後的正式 25-PSF MAT、768 組配對、從零 8192 次訓練、930 張實拍與 8370 顆圓量測皆已完成；`results/final_audit.json` 通過。
- 指定來源位置：`D:\GMM_2_Final\PSF_Fitting\output\20260924_center9_psf\PSF_20260924_center9_25_normalized.mat`，**正式修正後 SHA-256** `a41413274d4134588070216f9699fd985b986c2419ae895ef6eabce0d0937231`。先前同名檔的 SHA-256 `3e6889b5c36488e426415c01e99df12c5a12fd9a908d52cb20f4fd1434c201c5` 已移入 `diagnostics_prior_orientation/`，不得用作本輪正式銀行。
- 本包新銀行 SHA-256：`4435f52a5d0f3ee31b5fbcbfbf13817d4ce2cabeeb2279b64b9492f9f3e4af7b`。核數值與來源 MAT 逐項相同，明暗亮度係數留在來源記錄中，不混入單顆正規化 PSF。
- 正式檔案出現後核對 25 顆 101×101、單顆和為 1、物面像素 0.1725 µm、來源照片與九顆 SEM 對應、擬合保留柱檢查及來源雜湊。列優先 5×5：索引＝列×5＋欄；亮度係數不混入正規化 PSF。
- 資料和模型規格：與 R143 同 768 個清楚母場景及分組、雜訊、逐場景 PSF 索引、架構、訓練種子和 8192 次更新。配對資料由新銀行重新製作，已通過逐場景對照；來源鎖建立後，完整訓練從零啟動。
- 最終模型保存點：`runs/formal_8192/checkpoints/step08192.pth`，SHA-256 `c112d59e1d3efbb281059ca443bebf26c1ce7202e9b586740bca7b86d001ab41`。`verify_package.py --mode infer-ready` 通過；單張推論與批次輸出逐值相同。
- 修正九顆 SEM 編號的校準尺寸檔 `evaluation/sem_current_center9_mapping.csv`，SHA-256 `a71469bcc9105a77aae6b1a4a00af38433ededf673f8bae1f2f193520d9cd89b7`。本輪 Excel 九顆平均 2629.737 nm；舊輪廓點位參照為 2614.439 nm，兩者分表保存。
- PSF 的 SEM 尺寸是光學校準輸入；神經訓練標籤仍為合成清楚影像。使用同 SEM 表的尺寸對照不作獨立準確度宣稱。
- 固定實拍：30 趟×31 張，九顆圓、PI 軸及同一 ACM／LSC 讀法。R143、R140v2、RAW 等原量測不改動。
- D 槽保留程式、資料、權重與表格；H 槽 `active_runs/R145_Center9PSF25_CorrectedPairs/reconstruction` 留給 930 張浮點影像與收據。無正式基準自動升級。
- [完整結果](reports/R145_RESULTS.md)、[位移與尺寸追查](reports/R145_STABILITY_FOLLOWUP.md)、`results/position_stability_followup.json`、`results/cli_replay/first_frame.npz` 均已產出。
- [PSF 效益受限的深入分析](reports/R145_PSF_LIMITING_MECHANISMS.md)保留頻域錯位、實拍光學分支開關、全數 206 組 PSF 可辨識訊號、兩批拍攝條件及細位移測試的獨立核對；明細在 `results/deep_diagnosis/`。這是 R145 完成後的診斷，不改正式權重或原量測表。
