# 資料盤點

## 採用資料

- PSF stack：`PSF_Fitting/Crop_circle_FreqFiltered/Fits/PSF_fitted_2D_FOVstack.mat`
- 批次摘要：`PSF_Fitting/Crop_circle_FreqFiltered/Fits/batch_results.csv`
- 選擇原則：使用明確指定的資料路徑。

## 資料完整性

- `psf_grid` 尺寸：`(101, 101, 1, 100)`
- FOV 格點數：`1 x 100`
- `batch_results.csv` 筆數：`100`

## 判讀

- 目前掃描到的 Whole-FOV 結果為成對 `.mat` 與 `.csv`，足以產出 montage、代表位置比較、fval heatmap 與簡表。
- 若後續出現更新的 Whole-FOV 結果，可直接重新執行此腳本，會再次依同目錄配對、完整度與時間排序重新挑選。
