# R152較早獨立包：原NPZ資料介面

這份GitHub閱讀說明補於2026-10-22；原使用說明在[start_here.py](start_here.py)，原程式和設定未改。它保留較早NPZ資料讀取方式；日後要從程式生成TIFF訓練影像，先看[影像生成版](../R152_Standalone_ImageFiles_20261004/README.md)。

此包的模型與[settings.py](settings.py)、必要25PSF及固定權重一起使用，不能只複製程式就宣稱完整可執行。來源取得見[附件指南](../../docs/reproducibility/ASSET_GUIDE.md)，原資料界線見[reference_info.py](reference_info.py)。768個場景／3072視圖的原資料可生成，不再為這個舊介面重傳整套。

原`train.py`預設從已訓練主體做8192次擴充，`--from-scratch`才是兩階段；`infer.py`讀灰階影像，輸出原生NPZ與顯示PNG。新結果按原設定寫`outputs`。需要操作時先完整讀原說明、備好必要來源並使用新副本；本次沒有執行訓練或推論。

本專案目前論文仍以[R153交接](../../Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md)為入口；便攜包可使用不等於所有模型效果或絕對準確度均已被證明。
