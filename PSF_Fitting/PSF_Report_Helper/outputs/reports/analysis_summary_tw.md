# Whole-FOV PSF 分析摘要

## 分析範圍

- 本次分析採用 `PSF_fitted_2D_FOVstack.mat` 與 `batch_results.csv`，針對 `psf_grid`、`fval_map` 與 `iterations_map` 生成報告型圖表。
- FOV 版圖為 `1 x 100`，可直接反映全視野擬合後的 PSF 形貌分布。

## 主要觀察

- `fval` 平均為 `1426.01`，標準差 `65.71`，範圍 `1291.49` 到 `1685.89`，表示全視野擬合品質存在可觀的空間差異。
- `iterations` 平均為 `581.0` 次；單張計算時間平均 `34.99` 秒。
- 中心位置 (R1, C51) 的二階矩寬度約為 `X=7.92`, `Y=7.96`；邊緣位置與角落位置分別為 `(7.93, 7.96)` 與 `(7.91, 7.95)`。
- 代表位置比較圖提供 2D PSF 與中心 X/Y 剖面，可快速判讀是否有視野邊界變寬、拉伸或非對稱現象。

## 建議放入報告的圖表

- `figures/psf_montage.png`：呈現全視野 PSF 整體分布。
- `figures/psf_montage_log_normalized.png`：壓縮動態範圍後更容易比較側瓣與外圍擴散。
- `figures/psf_representative_comparison.png`：用中心、邊緣、角落三個代表點說明視野位置差異。
- `figures/fval_heatmap.png`：對應擬合誤差在視野上的空間變化。

## 備註

- `batch_results.csv` 共 `100` 筆，與 MAT 內 `fval_map` / `iterations_map` 可互相對照。
- 目前資料已足以形成 1 到 2 頁研究成果報告的核心圖文；若需要更完整因果解釋，仍需回到光學與 Zernike 係數層級做補充。
