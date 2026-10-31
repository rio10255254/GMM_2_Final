# 原始資料

[專案首頁](../README.md) · [按用途取得檔案](../docs/reproducibility/ASSET_GUIDE.md) · [目前保存狀態](../docs/reproducibility/STATUS.md)

這裡放換不回來的東西：相機拍的原圖、平台記下的位置、電子顯微鏡量的尺寸、人工標的參照。好幾輪實驗共用的資料只存一份，各輪都指向這裡。

大部分影像本身放在 Releases 附件，git 裡是說明檔。每個子資料夾的 README 都寫了內容是什麼、在哪個附件、怎麼取回。

## 相機原拍與儀器紀錄

| 資料 | 是什麼、拿來做什麼 | 打開 |
|---|---|---|
| 2026-09-03 位移重拍 | 論文的主要考題。30 趟，每趟一個起點加 30 步，共 930 張照片，加上 30 份平台記下的位置 | [原拍與拍攝順序](PI_Repeatability_20260903/README.md)、[平台位置原表](PI_Repeatability_20260903/position_records/README.md) |
| PSF100 原拍 | 2025-09-03 拍的 395 張，其中 100 個視野用來量出最早那一版 PSF。跟 2026 年的位移重拍是兩回事 | [逐張來源與擬合對照](PSF_Camera_Acquisitions/PSF100_20250903/README.md) |
| PSF100 同日棋盤 | 同一天、同一台相機另外拍的 393 張棋盤格，當時拍來做什麼沒有紀錄 | [同日棋盤原拍](PSF_Camera_Acquisitions/PSF100_20250903/README.md#同日棋盤原拍2026-10-28-補) |
| 廠商的圓環位移序列 | 2025-10-29 拍的六組序列，另外有模型實際讀的裁切版 | [原拍與裁切](NTU_Originals/README.md) |
| 0615 三輪 PSF 取像 | 三輪各 242 張，共 726 張。同一位置拍兩張、當時擬合怎麼用，都有紀錄 | [原拍、處理過的輸入與取回方法](PSF_Camera_Acquisitions/README.md) |
| Lab 25 位置校正 | 實驗室那台顯微鏡的 25 張校正原拍，2026-06-05 拍。舊路徑名稱寫成 20250605，是當時的名字，沒有改 | [校正補件與取回](../docs/reproducibility/priority_sources_20261022/README.md) |
| Step、多倍率等實拍 | Step 樣品、100MG 50×、20×、5× 的實拍原圖 | [實拍原拍與取回位置](Real_Sample_Captures/README.md)、[每批照片的來源與用途](../docs/reproducibility/SOURCE_AND_IMAGE_DECISIONS.md) |
| 2026-09-24 中央九點 PSF | 25 張原拍加上拍攝紀錄 | [原拍與取回](PSF_Camera_Acquisitions/20260924/README.md) |

## 量測、人工參照、固定的比較輸入

| 資料 | 為什麼要留 | 打開 |
|---|---|---|
| 電子顯微鏡（SEM）原工作表 | 尺寸和輪廓的參考答案。注意有些輪次也拿它來校正，用到時要一起看那一輪的說明 | [SEM 原件](SEM_Originals/README.md) |
| R61 v16 外部 GMF 量測包 | 廠商兩組序列的 GMF 原始分數，加上當時送去量的影像。量測工具已經不在了，沒辦法重新量，所以整組留下 | [量測包](NTU_Originals/README.md) |
| 30 份原圖邊界點 | 當時量到的邊界座標，R129、R130 等輪拿來比較。只有座標，不是整張還原影像 | [原邊界與固定小圖](../docs/reproducibility/priority_sources_20261022/README.md) |
| 歷史幾何與固定裁切 | 當年實際用的輸入。今天重新裁一次，結果不一定一樣，所以留原件 | [歷史固定輸入](Legacy_Frozen_QA_Inputs/README.md) |
| 跨輪固定參照與診斷 | R32、R113／R116、R131／R132 和 SEM 方向的候選。其中有些是模型輸出，不是相機拍的 | [逐項用途與取回](../docs/reproducibility/round_source_followthrough_20261022/README.md) |

## 早期的環形輸入

R33、COMBO、R39、R40 共用的輸入在 [Baseline_Ring_Inputs](Baseline_Ring_Inputs/README.md)：1,000 組來源已經說不清楚怎麼生成的原件，和 100 組用 PSF 處理過的輸入分開保存。整套可以重新生成的訓練庫沒有上傳。

## 可以重新生成的大資料

訓練影像和整批還原結果，先查[生成程式、設定與需要的來源](../docs/reproducibility/GENERATION_GUIDE.md)。R108 的兩套資料已經驗證過，用取回的程式能生成出一模一樣的檔案。R61 的 3,400 組舊來源和歷史幾何就只能用原件，光留亂數種子不夠。

照片、處理過的輸入、合成資料、模型輸出、量測座標是不同的東西，用的時候要分清楚。某一輪有沒有用過參考答案、算不算獨立驗證，以那一輪的正式報告為準。
