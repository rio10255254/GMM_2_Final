# 新 PSF 擬合結果重訓與封包既有效果比較

日期：2026-03-26  
比較目的：在不改動主分析定義的前提下，檢查「吃新 PSF 擬合結果後重訓出的新模型」與「封包內既有正式效果」在同一張 Demo 圖上的差異。

## 比較對象

- 舊版封包既有效果
  - 推論輸出：
    `_deployment_package/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/輸出結果/推論結果/reconstruct_progress_r26_sm035_best_tradeoff_in_Demo_Input_20260324_233331`
  - 單張分析：
    `_deployment_package/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/analysis_single_image_recon`
- 新版 PSF 重訓效果
  - 使用的新 PSF：
    `PSF_Fitting/Crop_circle_FreqFiltered/Fits/PSF_fitted_2D_FOVstack.mat`
  - 新訓練輸出：
    `_deployment_package/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/輸出結果/訓練結果/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260326_093223`
  - 新推論輸出：
    `_deployment_package/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/輸出結果/推論結果/reconstruct_progress_best_tradeoff_in_Demo_Input_20260326_093223`
  - 新單張分析：
    `_deployment_package/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/analysis_single_image_recon_newpsf`

## 新 PSF 採用依據

- 封包原 PSF 路徑：
  `_deployment_package/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/內部檔案/PSF_Fitting/Crop_circle_FreqFiltered/Fits/PSF_fitted_2D_FOVstack.mat`
- 舊版封包 PSF SHA256：
  `3AAB9CC1ED9EE0EB9C85227D026A3A8D86D0C035B8D06A46EB688551EFAE79CD`
- 新版正式 PSF 來源：
  `PSF_Fitting/Crop_circle_FreqFiltered/Fits/PSF_fitted_2D_FOVstack.mat`
- 新版正式 PSF SHA256：
  `F54F75F191AFEE507EA7BE9F5B561A465590A94DFDDD72EF722818D48E82E673`
- 舊版封包 PSF 備份：
  `_deployment_package/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/輸出結果/比較結果/psf_swap_20260326_093203/PSF_fitted_2D_FOVstack.package_old.mat`
- 根專案正式 PSF 的 `formal_config.json` 顯示此結果已由 ValidationLab 候選提升為目前 Whole-FOV 正式輸出，生成時間為 `2026-03-26 09:23:57`，並使用 `warm_start + pre_alignment + tilt locked`。

## 執行方式

- 封包內訓練入口已可直接使用，`doctor` 檢查確認目前環境為 native route，Python 為 `C:\Users\Rio\anaconda3\python.exe`，GPU 為 `NVIDIA RTX A6000`，裝置可用 `cuda:0`。
- 以新 PSF 替換封包內既有 `PSF_fitted_2D_FOVstack.mat` 後，執行完整重訓。
- 重訓完成後，使用新訓練目錄中的 `best_tradeoff.pth.tar` 對 `Demo_Input` 做推論。
- 單張分析比較採用與舊版相同的 RAW 影像、相同 Demo 樣本、相同 ROI 座標與相同 metric 定義。
- 由於目前單張分析腳本的 auto ROI 流程會在套用 override 前先失敗，本次新 PSF 版分析改用舊版 ROI 座標直接覆寫，以確保新舊比較公平，不重新挑 ROI。

## 新訓練與新推論輸出

- 新訓練開始時間：`2026-03-26 09:32:23`
- 新訓練目錄：
  `_deployment_package/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/輸出結果/訓練結果/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260326_093223`
- 本次推論使用權重：
  `_deployment_package/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/輸出結果/訓練結果/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260326_093223/weights/best_tradeoff.pth.tar`
- 權重檔時間：
  `best_tradeoff.pth.tar` = `2026-03-26 09:41:32`
- 新推論輸出：
  `_deployment_package/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/輸出結果/推論結果/reconstruct_progress_best_tradeoff_in_Demo_Input_20260326_093223`

## 單張分析對照表

說明：下表只比較「舊版封包正式 R26 輸出」與「新版 PSF 重訓後輸出」，RAW 數值相同，因此不重複列入主表。`delta = 新版 - 舊版`。

| 指標 | 舊版封包 R26 | 新 PSF 重訓 R26 | delta | 判讀 |
|---|---:|---:|---:|---|
| edge_width_main_px | 33.4741 | 36.2600 | +2.7859 | 主邊界變寬，退步 |
| edge_width_weak_px | 34.0101 | 49.0800 | +15.0699 | 弱邊界明顯變寬，退步 |
| max_slope_main | 6.4505 | 4.3940 | -2.0565 | 主邊界轉換變鈍，退步 |
| max_slope_weak | 5.2905 | 2.0769 | -3.2135 | 弱邊界轉換變鈍，退步 |
| CNR_main | 19.5539 | 9.1935 | -10.3604 | 局部對比下降，退步 |
| CNR_weak | 33.3378 | 7.7921 | -25.5457 | 弱邊界局部對比明顯下降，退步 |
| background_std | 0.6529 | 1.0903 | +0.4374 | 背景波動上升，退步 |
| background_grad_p95 | 3.1623 | 3.1623 | +0.0000 | 背景高梯度指標持平 |
| HF_ratio | 0.0103 | 0.0164 | +0.0060 | 固定高頻帶能量佔比略升，不可直接視為優勢 |
| checkerboard_ratio | 0.1208 | 0.2148 | +0.0940 | 棋盤格傾向指標變差 |
| edge_continuity_ratio | 0.9944 | 0.2667 | -0.7278 | 連續性指標大幅變差 |
| ring_thickness_std_px | 4.2530 | 1.5523 | -2.7007 | 厚度一致性改善 |

## 結果解讀

### 1. 主證據：邊界集中化明顯退步

- 若沿用之前單張分析的主證據鏈，最重要的是 `edge_width_*` 與 `max_slope_*`。
- 這次吃新 PSF 後重訓出的新模型，在主邊界與弱邊界上都比舊版封包 R26 更差：
  - 邊界寬度變大
  - 邊界斜率下降
- 因此，若只看這張 Demo 圖，本次新 PSF 重訓結果**沒有維持住舊版 R26 的邊界集中效果**。

### 2. 對比與背景：沒有換到更乾淨且更清楚的平衡

- `CNR_main` 與 `CNR_weak` 都明顯低於舊版封包 R26。
- `background_std` 從 `0.6529` 回升到 `1.0903`，表示背景波動變大。
- `background_grad_p95` 雖持平，但這不足以抵銷 `CNR` 與 `edge profile` 的退步。
- 因此，本次新 PSF 重訓結果也**沒有在「邊界集中 + 背景抑噪」這條主證據鏈上優於舊版效果**。

### 3. 頻域：不能寫成高頻更好，反而更像副作用增加

- 本流程中的 `HF_ratio` 是固定高頻帶 `r=0.35–0.60` 的能量佔比，較接近固定高頻帶/噪聲帶能量，不宜直接當成有效細節量。
- 新版 `HF_ratio` 略升，`checkerboard_ratio` 也明顯升高。
- 這組結果不支持「高頻品質更好」；更保守的說法是：**新 PSF 重訓版沒有比舊版更乾淨，且在假高頻傾向指標上反而較差**。

### 4. 幾何 proxy：只有厚度一致性改善，不能蓋過主證據退步

- `ring_thickness_std_px` 從 `4.2530` 降到 `1.5523`，代表固定 RAW 幾何參考下，環厚度分布更一致。
- 但 `edge_continuity_ratio` 從 `0.9944` 大幅降到 `0.2667`。
- 依目前主分析設計，`ring_thickness_std_px` 可視為一個正向訊號，但不足以扭轉 edge profile、CNR、背景波動與 checkerboard ratio 的整體退步。

## 總結

在封包內既有資源下，這次已成功完成以下流程：

1. 從根專案取用最新正式 PSF 擬合結果。
2. 替換封包內 PSF 並保留舊版備份。
3. 以封包內既有訓練流程完成完整重訓。
4. 以新 checkpoint 完成 Demo_Input 推論。
5. 以與舊版相同的 ROI 與 metric 定義完成單張分析比較。

就目前這張 Demo 圖的對照結果而言，**新 PSF 重訓版並沒有優於封包內原本保留的正式 R26 效果**。  
最主要的退步集中在：

- 邊界變寬
- 邊界斜率下降
- CNR 下降
- 背景波動升高
- checkerboard ratio 變差
- edge continuity 明顯下降

目前唯一明顯正向的幾何 proxy 是 `ring_thickness_std_px` 下降，但不足以支撐「整體效果已優於舊版」的結論。

## 建議下一步

- 若目標是讓封包最終只保留吃新 PSF 的版本，現階段不建議直接覆蓋掉舊版效果的比較證據。
- 建議先保留本報告、舊版單張分析與新 PSF 版單張分析，作為後續繼續調整訓練策略或 checkpoint 選擇的對照基準。
- 若要繼續追新 PSF，下一步應優先檢查：
  - 是否最佳 checkpoint 不在目前 `best_tradeoff`
  - 新 PSF 對 loss balance 或 physics weight 的影響是否需要重新調整
  - 是否需要重新檢查 train/val 的選模準則，而不是直接沿用舊 PSF 時代的 best-tradeoff 判準
