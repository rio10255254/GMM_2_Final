# Full 100 正式候選結果摘要

- 候選流程：`warm_start + refined pre_alignment (prealign_step = 0.25) + tilt locked`
- 候選輸出：`PSF_Fitting/PSF_Fitting_ValidationLab/outputs/final_candidate_full100`
- 對照表：`PSF_Fitting/PSF_Fitting_ValidationLab/outputs/tables/final_candidate_full100_vs_original.csv`
- 偏移比較圖：`PSF_Fitting/PSF_Fitting_ValidationLab/outputs/figures/final_candidate_full100_peak_offset_comparison.png`

## 核心結果

- 原始 Whole-FOV 輸出的 mean fval 為 1578.782；修正版候選降為 1426.007，約下降 152.775。
- 原始結果的 mean abs peak offset 為 2.000 px，修正版候選降為 0.620 px。
- 原始結果的 mean peak offset 約為 (y=-1.000, x=1.000)，呈現明顯共同偏移；修正版候選降到 (y=0.010, x=-0.570)。
- 原始結果只有 1 個 peak 位置，而且最常見 peak 位置 `(49, 51)` 出現 100 次；修正版候選增加到 6 個 peak 位置。
- 原始結果的 pairwise PSF correlation 最低值為 0.999935，顯示 PSF 幾乎同形；修正版候選最低值降到 0.983719，表示 Whole-FOV 間的形狀差異開始被保留下來。

## 解讀

- 這次修正有效消除了原本「整批 PSF 一起偏掉」的主要問題。
- 修正版候選仍保留相近的平均執行時間，但以更低的 fval 換得更接近中心的 PSF 主峰位置。
- 原始輸出幾乎把 100 個位置都壓成同一顆偏移 PSF；修正版候選則開始恢復 Whole-FOV 之間的空間差異。
- 目前最合理的正式修正版方向，已可收斂為：在原始 Whole-FOV 擬合流程之外，先加入 refined pre_alignment，並維持 tilt locked。
