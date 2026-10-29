# 跨輪實拍分析

不屬於單一實驗輪、各輪會共用的實拍分析。2026-10-28 重整時從根目錄集中到這裡，各資料夾的內容與名稱都沒有改。分析用的相機原拍在 [Shared_Sources/Real_Sample_Captures](../Shared_Sources/Real_Sample_Captures/README.md)。

| 資料夾 | 是什麼 |
|---|---|
| [Step_analysis_20260623](Step_analysis_20260623/README.md) | Step 樣品的位移、尺寸與形狀分析 |
| [20260702_100MG_displacement_analysis](20260702_100MG_displacement_analysis/README.md) | 100MG 樣品 50× 的位移分析 |
| 20260702_100MG_phase_dft_analysis_matlab | 同一批 100MG 影像以 MATLAB 相位 DFT 算的位移、最佳 30 張的比較圖與 ROI 預覽（只有這 10 張圖） |
| [20260704_20x_5x_analysis](20260704_20x_5x_analysis/README.md) | 20× 與 5× 實拍的分析 |
| [Reconstruct_Progress](Reconstruct_Progress/README.md) | 較早共用的重建與分析入口 |
| [AnalysisLab](AnalysisLab/README.md) | 分析工具的版本與入口 |

兩個位移分析資料夾裡，每次執行留下的 `_r61_real_sample_runtime_*` 快照收在各自的 `_r61_real_sample_runtime/` 子資料夾裡，名稱不變，一個都沒刪。
