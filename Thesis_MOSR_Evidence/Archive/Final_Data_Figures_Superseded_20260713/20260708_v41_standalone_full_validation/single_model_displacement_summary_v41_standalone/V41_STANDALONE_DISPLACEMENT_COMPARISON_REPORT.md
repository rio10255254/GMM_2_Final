# V41-Standalone 單一模型位移比較整理

本資料夾只保留 Raw 與最新單一 V41-Standalone 模型的比較，方便論文第六章直接引用。
主要判讀以全部步數為主；common best-30 只作為補充，表示在兩者共同較乾淨的步數上比較。

## 全部步數主表

| 資料集          |   步數 |   Raw標準差(nm) |   V41標準差(nm) |   穩定性改善(%) |   Raw中位誤差(nm) |   V41中位誤差(nm) |   中位誤差改善(nm) | 判讀                                          |
|:----------------|-------:|----------------:|----------------:|----------------:|------------------:|------------------:|-------------------:|:----------------------------------------------|
| 50x 0.5 um/step |     50 |           38.53 |           38.47 |            0.14 |              5.85 |              4.61 |               1.24 | small but consistent improvement              |
| 50x 1 um/step   |     49 |           12.89 |           10.81 |           16.17 |              9.34 |              8.42 |               0.92 | clear stability improvement                   |
| 20x 0.5 um/step |     49 |           80.23 |           80.45 |           -0.28 |              9.72 |              9.39 |               0.33 | median error improved but stability did not   |
| 20x 1 um/step   |     49 |           25.66 |           25.3  |            1.4  |              8.74 |             10.23 |              -1.49 | stability improved but median error increased |
| 5x 0.5 um/step  |     49 |           11.36 |           11.65 |           -2.56 |             42.95 |             41.51 |               1.44 | median error improved but stability did not   |
| 5x 1 um/step    |     49 |          157.26 |          157.48 |           -0.14 |            158.82 |            157.39 |               1.43 | median error improved but stability did not   |

## 共同最佳 30 步補充表

| 資料集          |   步數 |   Raw標準差(nm) |   V41標準差(nm) |   穩定性改善(%) |   Raw中位誤差(nm) |   V41中位誤差(nm) |   中位誤差改善(nm) | 判讀                                        |
|:----------------|-------:|----------------:|----------------:|----------------:|------------------:|------------------:|-------------------:|:--------------------------------------------|
| 50x 0.5 um/step |     30 |            4.09 |            3.48 |           14.84 |              3.37 |              2.44 |               0.93 | clear stability improvement                 |
| 50x 1 um/step   |     30 |            7.07 |            5.74 |           18.9  |              6.43 |              5.65 |               0.78 | clear stability improvement                 |
| 20x 0.5 um/step |     30 |            6.79 |            7    |           -2.98 |              4.32 |              5.59 |              -1.27 | no improvement                              |
| 20x 1 um/step   |     30 |            6.01 |            6.35 |           -5.77 |              5.53 |              7.34 |              -1.81 | no improvement                              |
| 5x 0.5 um/step  |     30 |            6.5  |            6.8  |           -4.59 |             39.46 |             36.48 |               2.97 | median error improved but stability did not |
| 5x 1 um/step    |     30 |           67.91 |           67.69 |            0.31 |             90.2  |             89.25 |               0.95 | small but consistent improvement            |

## 圖檔

- figures/all_steps_std_nm_by_dataset.png：全部步數位移標準差比較。
- figures/all_steps_improvement_pct.png：全部步數穩定性改善比例。
- figures/all_steps_std_nm_by_magnification_panels.png：三個倍率分開顯示的全部步數穩定性圖。
- figures/common_best30_std_nm_by_dataset.png：共同最佳 30 步標準差比較。
- figures/step_trace_*.png：各倍率、各位移量逐步折線圖。

## 來源

- source_all_steps: Thesis_MOSR_Evidence/Final_Data_Figures/20260708_v41_standalone_full_validation/boundary_sensitive_roi_v41_compare/tables/boundary_sensitive_all_steps.csv
- generated_at: 2026-07-08T22:52:23