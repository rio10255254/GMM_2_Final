# 2026年6月15日的三輪拍攝與Step

三輪Circle資料各242張：11×11位置、每位置連拍兩張，共726張5120×5120相機原圖。原檔名保存毫秒時間；[726張清單](ORIGINAL_726_FRAMES.csv)列明輪次、位置、兩張連拍與內容核對值。分組對應已與三份原準備紀錄的第一張來源逐一比對。

| 輪次 | 第一張 | 最後一張 | 後續用途 |
|---|---|---|---|
| Round1 | 16:32:17.629 | 16:51:20.217 | 正式L0錨點及三輪比較 |
| Round2 | 16:52:36.234 | 17:07:26.796 | L1來源診斷 |
| Round3 | 17:08:55.762 | 17:24:57.698 | L1來源診斷 |

## 拍了多少與實際擬合多少

[原執行程式](../../../PSF_Fitting/quick_recalibration/validation_experiments/L0_newdata/run_L0_newdata_rounds.m)每輪取第1張，選位置1、6、11、56、61、66、111、116、121，各重複15次。6月16至17日保存了45組執行、405筆擬合；不是所有121位置及兩張連拍都完成擬合。

[準備程式](../../../PSF_Fitting/quick_recalibration/validation_experiments/l0_newdata_tools.py)會找中心、裁切、處理中心黑塊並建立圓邊界範圍。[Round1對照](../../../PSF_Fitting/quick_recalibration/validation_experiments/L0_newdata_round1/inputs_primary/prep_manifest.json)、[Round2](../../../PSF_Fitting/quick_recalibration/validation_experiments/L0_newdata_round2/inputs_primary/prep_manifest.json)、[Round3](../../../PSF_Fitting/quick_recalibration/validation_experiments/L0_newdata_round3/inputs_primary/prep_manifest.json)保留當年來源和中心座標。363張可再產生的處理圖保留本機；這次不再整批上傳第二套影像。

每位置第2張用於363對[連拍差異檢查](../../../PSF_Fitting/quick_recalibration/validation_experiments/L1_paired_frame_check/paired_frame_summary.md)，不代表另做了PSF擬合。同資料重複擬合與重新拍攝三輪是不同問題；[原L1摘要](../../../PSF_Fitting/quick_recalibration/validation_experiments/L1_newdata/README_TW.md)不支持絕對校準正確或儀器完全不變的主張。

## 同日另一批Step

788張Step照片已有GitHub原附件，並非這726張Circle原拍的另一個名稱。本次[完整既有位置表](STEP_EXISTING_PROVIDERS.json)讓兩組可分別追查；沿用既有保存和核對紀錄，這次不重傳整組Step。其位移、尺寸與論文解讀見[Step分析入口](../../../Step_analysis_20260623/README.md)。

返回：[原拍總入口](../README.md)。
