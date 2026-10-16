# Sensitivity Analysis

這裡放的是「BADS 擬合後，我檢查哪些參數會真的影響 PSF」的論文材料。

建議論文使用方式：

- `figures/parameter_shape_sensitivity_rank.png`：呈現各參數對 PSF 形狀的影響排序。
- `figures/top_parameter_diff_maps_fov061.png`：呈現代表性視野位置中，主要參數改變時 PSF 形狀如何變化。
- `figures/best_fit_shape_response_rank.png`：呈現實際擬合點附近，哪些參數變動比較有反應。
- `figures/best_fit_loss_saf_rank.png`：呈現實際擬合點附近，哪些參數會讓擬合損失變差。
- `tables/parameter_sensitivity_summary.csv`：參數敏感度總表。
- `tables/best_fit_operating_saf_summary.csv`：實際擬合點附近的敏感度總表。

目前結果的讀法：

- 有些參數在純 PSF 形狀上看起來有反應，但被標記為不適合直接解讀，這些比較適合當限制說明。
- 論文主文可以保守地說：敏感度分析用來確認主要參數對 PSF 形狀與擬合穩定性的影響，並協助界定後續模型中可相信的 PSF 變化來源。
- 不建議把每個參數都當成獨立物理解釋，這部分比較適合用來支撐模型資料的可靠性。
