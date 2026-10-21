# Global BADS Fit

這裡放的是「我用 BADS 做全視野 PSF 擬合」這件事的論文材料。

建議論文使用方式：

- `figures/psf_montage_log_normalized.png`：看整個視野中 PSF 形狀如何隨位置變化，適合當主圖。
- `figures/fval_heatmap.png`：看每個視野位置的擬合品質分布，適合支撐「不是只挑單點展示」。
- `figures/psf_representative_comparison.png`：看代表性位置的擬合前後對照，適合放在方法或結果段落。
- `figures/center9_pillar_fit_20x_50x`：20× 與 50× 的交界旁中心九顆 pillar 擬合與驗證結果；每個倍率分別保存實拍九宮格、SEM-CD 真值、擬合 PSF、前向重建、固定 NSR = 0.05 的 Wiener 反卷積、MOSR 重建、邊緣剖面、CD 門檻敏感度、振鈴與頻譜圖。頻譜皆以實際傅立葉振幅計算並共用 -80 至 0 dBFS 顯示範圍。
- `source_data/center9_pillar_fit_20x_50x/v42_crop_rerun`：此資料夾名稱為既有追溯路徑；內容保留九宮格裁切座標、乾淨裁切輸入、MOSR 原始輸出與完整執行紀錄。
- `tables/summary_stats.csv`：已整理好的數值摘要，適合轉成論文表格。
- `tables/batch_results.csv`：每個視野位置的原始擬合結果表，適合追溯與補充資料。
- `source_data/PSF_fitted_2D_FOVstack.mat`：完整擬合出的 PSF 資料，後續模型使用時可追溯到這份來源。

這一段可以寫成：先由實驗影像擬合出全視野 PSF，再把這個結果作為後續模型與分析的基礎。
