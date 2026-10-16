# 單張影像重建分析規劃摘要

## 可用資料
- RAW：`D:\GMM_2_Final\_deployment_package\GeoEdge_R26_正式交付版\GeoEdge_R26_使用包\內部檔案\Demo_Input\VisionTop_20251029182653732.bmp`
- R26：`D:\GMM_2_Final\_deployment_package\GeoEdge_R26_正式交付版\GeoEdge_R26_使用包\輸出結果\推論結果\reconstruct_progress_r26_sm035_best_tradeoff_in_Demo_Input_20260324_233331\VisionTop_20251029182653732.bmp`
- RAW SHA256：`2a9dadc128b00a4bb285736eeb62405b08843ec8d3d90d807638a4fb3dcdf77f`
- R26 SHA256：`636866bb6639e06051b1ae67a81b09f290974d363673623b946cd1dbebe80fd9`
- 可重用邏輯：`detect_ring`、radial profile、ring ROI。
- 不納入：GMF、SSIM、PSNR、MTF、GLCM、wavelet、多版本比較。

## 主分析項目
- 整體比較圖：RAW vs R26。
- 4 類 ROI：主要邊界、缺陷區、弱邊界、背景區。
- Edge profile：主邊界與弱邊界各 1 條，固定平滑與 10%~90% width 定義。
- 頻域驗證：2D FFT、radial spectrum、HF ratio、checkerboard ratio。
- 幾何 proxy：edge_continuity_ratio、ring_thickness_std_px。

## 核心證據鏈
- 視覺對照建立直觀差異。
- Edge profile 證明邊界更陡、更集中。
- CNR 與 background_std 檢查改善不是靠背景惡化換來。
- FFT 與 checkerboard ratio 排除不自然高頻。
- 幾何 proxy 保守支持其對後續辨識/量測較有利。

## 最終圖與表
- 圖 1：整體比較圖，回答整張影像層級的直觀差異。
- 圖 2：ROI 放大圖，回答主要邊界、缺陷、弱邊界與背景的局部差異。
- 圖 3：Edge profile 圖，回答邊界是否更集中。
- 圖 4：頻域驗證圖，回答清楚是否可信、是否有假高頻。
- 表 1：總表，整合空間域、頻域與幾何 proxy 指標。

## 刻意不做的項目與原因
- GMF：本次明確排除外部程式。
- SSIM、PSNR、MTF：與本次無 GT 的單張證據鏈不相容或易被誤讀。
- GLCM、wavelet、統計檢定：篇幅成本高，但報告說服力增量低。
- 多版本比較：會把 RAW vs R26 主線打散。

## 可安全下結論的點
- 邊界是否更集中。
- 背景波動是否未明顯惡化。
- 是否未出現明顯 checkerboard/假高頻趨勢。

## 只能寫成趨勢的點
- 更接近真值。
- 真實解析度提升。
- 實際量測精度已被直接證明提升。