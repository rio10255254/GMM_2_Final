# PSF 報告撰寫輔助分析

這個資料夾提供一個最小可行的 Whole-FOV PSF 報告整理工具，目的不是重跑擬合，而是把既有擬合結果快速轉成可放進 1 到 2 頁 Word 研究成果報告的圖表、表格與繁體中文文字草稿。

## 執行方式

在 `D:\GMM_2_Final\PSF_Fitting` 下執行：

```powershell
python .\PSF_Report_Helper\run_report_analysis.py
```

若要明確指定資料來源，可使用：

```powershell
python .\PSF_Report_Helper\run_report_analysis.py `
  --mat-path .\Crop_circle_FreqFiltered\Fits\PSF_fitted_2D_FOVstack.mat `
  --csv-path .\Crop_circle_FreqFiltered\Fits\batch_results.csv
```

也可以只指定其中一個：

- 只給 `--mat-path` 時，腳本會先找同目錄的 `batch_results.csv`
- 只給 `--csv-path` 時，腳本會先找同目錄的 `PSF_fitted_2D_FOVstack.mat`
- 若同目錄配對檔不存在，腳本會直接報錯停止，不會繼續產生報告文字

## 主要資料來源

- `Crop_circle_FreqFiltered/Fits/PSF_fitted_2D_FOVstack.mat`
- `Crop_circle_FreqFiltered/Fits/batch_results.csv`

腳本會掃描 repo 內符合 Whole-FOV 命名的輸出，優先採用同目錄成對、較完整且較新的組合，並將判定結果寫入 `outputs/reports/data_inventory_tw.md`。
目前正式主線的預設來源就是 `Crop_circle_FreqFiltered/Fits/` 內的最新輸出；若正式 PSF 結果在同一路徑下被更新，此工具重新執行後就會直接跟著刷新。
在正式產生輸出前，還會檢查 `psf_grid` 維度、`fval_map` / `iterations_map` 尺寸，以及 CSV 筆數是否與 FOV 格點一致；若不一致，會直接失敗並提示。

## 主要產出

- `outputs/figures/psf_montage.png`
- `outputs/figures/psf_montage_log_normalized.png`
- `outputs/figures/psf_representative_comparison.png`
- `outputs/figures/fval_heatmap.png`
- `outputs/tables/summary_stats.csv`
- `outputs/reports/data_inventory_tw.md`
- `outputs/reports/analysis_summary_tw.md`
- `outputs/reports/report_text_draft_tw.md`

## 建議先看

1. `outputs/reports/data_inventory_tw.md`
2. `outputs/figures/psf_montage.png`
3. `outputs/figures/psf_representative_comparison.png`
4. `outputs/figures/fval_heatmap.png`
5. `outputs/reports/report_text_draft_tw.md`

## 指標定義

- `peak`：各位置 PSF 的最大值。
- `正規化剖面`：取 PSF 中心列與中心行的強度分布，並以峰值正規化。
- `二階矩寬度`：用強度分布的二階矩估計 X/Y 方向寬度，方便比較中心、邊緣與角落位置的展寬差異。

## 限制

- 此工具只整理既有擬合結果，不修改原始 MATLAB fitting 流程。
- 若資料夾內未找到成對的 Whole-FOV `.mat` 與 `.csv`，腳本會停止並提示缺少輸入。

## 測試

- Python 單元測試已統一集中於 `D:\GMM_2_Final\PSF_Fitting\tests\python\test_report_analysis.py`
- 在 `D:\GMM_2_Final\PSF_Fitting` 下可執行：

```powershell
pytest tests/python/test_report_analysis.py -q
```
