# 0309 已保存外部驗證基準

- 日期: `2026-03-09`
- seed label: `step8_curve_stdguard_v2`
- seed manifest: `Experiments/Legacy/organized_20260309/selected/current_seed.json`
- 權重: `Experiments/Legacy/organized_20260307/selected/runs/training_progress_GESR_v1_v5_ST8_SWP_stdg_20260307_135625/weights/best_tradeoff.pth.tar`
- 重建輸出: `Experiments/Legacy/organized_20260309/external_validation/current_seed/reconstructions/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260307_135625`
- 原始 GMF: `Experiments/Legacy/organized_20260309/external_validation/current_seed/gmf_results/raw/GMF_score.txt`

## POSY 步長統計

- 平均值: `8.021121 px`
- 標準差: `0.218730 px`
- CV: `2.7269%`
- 中位數: `8.020000 px`
- P05: `7.687000 px`
- P95: `8.362000 px`
- P05-P95 Span: `0.675000 px`
- 8px 平均誤差: `+0.021121 px`

## 結論

這版可作為 `0309` 後續續跑與外部比較的已保存基準：

- 視覺表現可接受
- 位移穩定性沒有被破壞
- 相較先前 `std≈0.488 px` 的結果，這次 `std≈0.219 px`，明顯更穩
- 但仍有進一步壓縮步長波動的空間
