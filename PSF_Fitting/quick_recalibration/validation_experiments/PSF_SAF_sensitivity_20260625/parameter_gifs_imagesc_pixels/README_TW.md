# PSF參數GIF說明

- 這批GIF使用 MATLAB 正式 ValidationLab PSF 流程產生每一幀PSF。
- x1 到 x14 每次只改一個參數，掃描 -0.02 到 +0.02，x15 固定為 1。
- x15 單獨掃描 0.80 到 1.20，用來顯示亮度振幅，不代表PSF形狀變化。
- matlab_style_heatmap_gifs 是最接近 slide-ready PSF heatmap 的版本：中心 31 x 31 裁切、parula 色盤、32 倍最近鄰放大，每幀各自正規化。
- matlab_style_heatmap_fixed_scale_gifs 使用同樣外觀，但全部共用固定亮度色階，max = 0.00960112258892；這組比較適合看 x15 亮度變化或不同幀的強弱差。
- raw_psf_gifs 是原始PSF強度動畫，固定強度色階，max = 0.00960112258892。
- diff_gifs 是相對 ideal PSF 的紅藍差異動畫；x1 到 x14 共用固定差異色階，abs max = 2.98755565065% of peak。
- diff_gifs_shared_enhanced_0p10pct 是公平的溫和增強版：所有參數共用 +/-0.10% peak 色階，讓中小變化比較容易看見。
- diff_gifs_shared_enhanced_0p02pct 是公平的強增強版：所有參數共用 +/-0.02% peak 色階，能讓更小的變化顯現，但大參數會飽和。
- x15 是亮度振幅，不是形狀參數，因此 x15 的 diff GIF 使用自己的振幅色階。
- 影像用 nearest-neighbor pixel blocks 放大，沒有做平滑或插值。
- 若要放進簡報並跟 l0_round1_median_psf_fov011_heatmap.png 那種風格一致，建議優先使用 matlab_style_heatmap_gifs。
- 若要一頁內公平比較且讓多幾個參數露出來，建議使用 diff_gifs_shared_enhanced_0p10pct；若要強調小參數的存在感，使用 diff_gifs_shared_enhanced_0p02pct。
- 若要保留完整大小排序，使用 diff_gifs；若要看單一小參數的變化形狀，使用 diff_gifs_enhanced_per_parameter，但這組不能拿來比較變化大小。
