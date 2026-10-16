# R144 來源、身分與保存

- **中止狀態：**搬移前 MAT 已被校準流程歸入 `diagnostics_prior_orientation/`，其原 SHA-256 與此包 `BANK_LOCK.json` 一致。正式訓練在第 160 次更新停止；只保存到第 128 次權重。`runs/formal_8192/ABORTED_SOURCE_SUPERSEDED.json` 是判讀本包的優先收據；不得稱完成 8192 次或完成實拍驗證。

- 類型：自包含研究實驗；原 R143 及 PSF 擬合成果不覆寫。
- 使用者指定 PSF：`D:\GMM_2_Final\PSF_Fitting\output\20260924_center9_psf\PSF_20260924_center9_25_normalized.mat`，SHA-256 `3e6889b5c36488e426415c01e99df12c5a12fd9a908d52cb20f4fd1434c201c5`。
- 本包 25 顆 NPZ 銀行 SHA-256：`998f2f19793727082da6fe00567567dc7640fdead0ea6f481ec270316659f5cb`。列優先 5×5，索引為列×5＋欄；原檔物面像素 0.1725 µm。
- 原 PSF 擬合的檢查：25 張來源影像、225 個圓位置、28 個來源檔雜湊及 25 顆正規化核均在原 PSF 資料夾的 `verification.json` 記為通過。本包轉換也重新核對 28 份來源雜湊。
- 既有 SEM 直徑用於 PSF 光學校準；神經訓練的目標仍是 R128 合成清楚場景，沒有 SEM 尺寸標籤。相同 SEM 表的後續尺寸比較屬同樣本、校準條件下的觀察。
- 配對資料：768 個 R128/R141 母場景；與 R143 完全相同的清楚答案、分組、位移、雜訊設定、無模糊對照及逐母場景 PSF 編號。`data/manifest.json` 提供每個輸出的雜湊與來源。
- 模型來源：R143 的模型架構與訓練規格逐檔相同；只改實驗名稱、銀行和重新製作的模糊影像。`config/SOURCE_LOCK.json` 將在正式訓練前鎖定程式、銀行和資料清單。
- 固定實拍：同 30 趟×31 張、九顆圓、PI 軸、ACM／LSC 與兩個既有 SEM 位置對應；R143、R140v2、Raw 等原量測作不改動參照。
- 儲存：D 槽保留程式、新資料、訓練權重及量測；H 槽 `active_runs/R144_Center9PSF25_MatchedPairs/reconstruction` 保存 930 張全尺寸影像及逐張收據。
- 本輪完成不自動改動正式基準或聲稱絕對尺寸準確度。
