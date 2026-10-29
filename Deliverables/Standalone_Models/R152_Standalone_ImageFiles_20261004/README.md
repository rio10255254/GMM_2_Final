# R152論文版：可重新產生訓練影像的獨立程式

這份GitHub閱讀說明補於2026-10-22；原包用[start_here.py](start_here.py)及[generation_guide.py](generation_guide.py)提供操作說明，原程式保持原樣。此版與本專案R152論文來源相連，不是H槽另一個專案同名R152。

## 保存內容與必要來源

`models`是R152模型，`core`是資料／損失／訓練工具，`generation`保留原場景、位移、25PSF成像及幾何生成。原始五份程式在`generation/original_sources`，實際入口是根層[generate_data.py](generate_data.py)，不需要讀者改寫舊原始路徑。

GitHub程式樹不附整套9216張訓練TIFF。先按[附件指南](../../../docs/reproducibility/ASSET_GUIDE.md)取得必要25PSF及固定模型，依原清單恢復相應位置；只有程式而缺`calibration/psf25_bank.npz`仍不能生成這份原資料。要查看數字結果通常不需要先生成資料或下載模型。

## 日後重新製作資料

原流程需要numpy、scipy及Pillow；原完整環境見[generation/recipe.py](generation/recipe.py)。在新的程式／輸出位置操作：

```powershell
python generate_data.py --output-dir outputs/generated_data --workers 2
```

原配方含512個訓練、128個開發、128個測試場景，每個4視圖，共3072張清楚、3072張無噪模糊與3072張幾何TIFF。來源由種子、原25PSF及配方產生，不需額外SEM或清楚相片；原取樣、光度、位移及捨入順序都由程式保留。

中斷可依原說明用`--resume`，已有結果可用`--verify-only`檢查；遇到不同內容會停止，不把新資料冒稱原資料。完整生成是日後實驗選項，本次文件整理沒有執行它。

## 模型與訓練的界線

推論入口為[infer.py](infer.py)，固定設定見[settings.py](settings.py)。正式模型權重與原25PSF都需先備妥。原`train.py`預設只訓練R152擴充8192次，使用既有主體；`--from-scratch`才是兩階段各8192次，`--updates`是累計總數。這些是原方法說明，不是本次啟動訓練的指示。

[verification_info.py](verification_info.py)保留以前完整9216張TIFF生成及短測／接續的實際範圍，並明記正式8192訓練沒有重跑。不同包／日期的核對不要統稱所有歷史已重做。原完整論文結論回[R153交接](../../../Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md)。
