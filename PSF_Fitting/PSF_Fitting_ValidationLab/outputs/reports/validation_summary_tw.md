# Whole-FOV PSF 驗證摘要

- 重新聚合時間：2026-03-27 17:34:59
- 已納入完成實驗：alignment_quarter_rep16, alignment_subpixel_rep16, alignment_rep16, alignment_tilt_rep16, baseline_rep16
- 子集代表點：fi=1(R1C1), fi=4(R1C4), fi=6(R1C6), fi=10(R1C10), fi=31(R4C1), fi=34(R4C4), fi=36(R4C6), fi=40(R4C10), fi=51(R6C1), fi=54(R6C4), fi=56(R6C6), fi=60(R6C10), fi=91(R10C1), fi=94(R10C4), fi=96(R10C6), fi=100(R10C10)

## 問題 1：raw/GT 預對齊是否能消除共同偏移
- 目前完成資料中，最能消除共同偏移的是 `alignment_quarter_rep16`。
- 這組的 mean peak offset = (y=0.062, x=-0.438)，mean abs peak offset = 0.500 px。
- 其 mean centroid offset = (y=0.057, x=-0.504)，mean abs centroid offset = 0.718 px。
- 這組對 raw 施加的平均預對齊位移為 (dy=0.906, dx=-0.906)。
- 和 `baseline_rep16` 相比，最佳對齊線把 mean abs peak offset 從 1.938 px 降到 0.500 px。
- 相比 `alignment_rep16`，`alignment_quarter_rep16` 把 mean peak offset_x 從 -0.812 壓到 -0.438，mean abs peak offset 從 0.812 px 降到 0.500 px。

## 問題 2：放開 tilt 是否能改善貼界
- 目前完成資料中，貼界指標最佳的是 `alignment_rep16`。
- 已納入實驗的 touches_edge 都是 0；目前代表子集上看不到 tilt 帶來額外貼界改善。
- `alignment_rep16` 的 mean edge energy ratio = 0.0026。

## fval 比較
- mean fval 最佳的是 `alignment_quarter_rep16`，數值 1433.239。
- `alignment_quarter_rep16` 相比 `alignment_rep16`，mean fval 再下降 52.865。
- `alignment_tilt_rep16` 相比 `alignment_quarter_rep16` 的 mean iterations 多 0.8，且 mean abs peak offset 0.812 px 對 0.500 px 沒有優勢。

## 最值得往正式可用版收斂的方向
- 綜合 offset、貼界與收斂品質，推薦 `alignment_quarter_rep16` 作為下一步正式候選。
- 目前最值得收斂的機制是：`warm_start + refined pre_alignment + tilt locked`。
- 目前不建議先把 tilt 放進正式主線：`alignment_tilt_rep16` 沒有帶來更好的 peak offset，且 mean iterations 比 `alignment_quarter_rep16` 高 0.8。

## 產出位置
- 比較表：`D:\GMM_2_Final\PSF_Fitting\PSF_Fitting_ValidationLab\outputs\tables\experiment_comparison.csv`
- 偏移比較圖：`D:\GMM_2_Final\PSF_Fitting\PSF_Fitting_ValidationLab\outputs\figures\representative_offset_comparison.png`
- fval/iterations 圖：`D:\GMM_2_Final\PSF_Fitting\PSF_Fitting_ValidationLab\outputs\figures\fval_iterations_comparison.png`
- candidate flow 說明：`D:\GMM_2_Final\PSF_Fitting\PSF_Fitting_ValidationLab\outputs\reports\candidate_flow_tw.md`
