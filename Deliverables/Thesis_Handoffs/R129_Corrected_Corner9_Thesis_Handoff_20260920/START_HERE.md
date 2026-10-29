# R129修正取樣位置後的獨立驗證與論文交接包

2026-09-20。相同新九顆、30次／930張；包含Raw對照、10張圖、完整明細、重新核對結果與R129不確定度分量。舊R128包與原始資料均保留。

1. [論文改寫交接說明](HANDOFF_FOR_THESIS.md)
2. [Raw／R129完整比較及圖表](01_Raw_R129_Comparison/README.md)
3. [R129不確定度分量解讀](02_R129_Uncertainty/README.md)
4. [修正後九顆位置](03_Sampling_and_SEM/selected_nine.png)
5. [平均曲線與波動帶主圖](01_Raw_R129_Comparison/figures/09_mean_error_sd_overlay.png)

每個子資料夾的CSV可獨立閱讀。04_Verification_and_Sources提供原邊界、圓心、徑向輪廓、固定模型記錄與本次核對；05只為分析程式副本，非完整獨立推論環境。

不包含930張全量原圖／重建或模型權重，來源位置留在設定與雜湊記錄。SEM逐顆方向仍為推定，並未因重新驗證而變成唯一證實；總不確定度缺項亦保留。verify_package.py使用標準Python核對根目錄MANIFEST.json。
