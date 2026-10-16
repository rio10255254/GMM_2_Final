# a025 vs COMBO 顯微重建簡報素材

日期：2026-05-13

## 用途

這個資料夾保存 a025 ONNX 與 COMBO ONNX 顯微重建比較的簡報素材。這些是內部展示/簡報素材，不放入公司 ONNX 交付包。

## 主簡報素材

- `ppt_ready\00_summary_a025_vs_combo.png`：整體比較摘要。
- `ppt_ready\01_defects_scratch_points.png`：主簡報，Defect and Scratch Preservation，PSNR 差異 +6.03 dB。
- `ppt_ready\02_large_region_boundary.png`：主簡報，Large-Area Boundary Reconstruction，PSNR 差異 +6.49 dB。
- `ppt_ready\03_mixed_micro_scene.png`：主簡報，Mixed Microscopy Field，PSNR 差異 +3.18 dB。
- `ppt_ready\04_curved_boundaries.png`：主簡報，Curvilinear Boundary Localization，PSNR 差異 +3.62 dB。
- `ppt_ready\05_thin_lines_junctions.png`：主簡報，Thin-Line and Junction Recovery，PSNR 差異 +3.24 dB。
- `ppt_ready\06_texture_retention.png`：主簡報，Local Texture Retention，PSNR 差異 +3.30 dB。
- `ppt_ready\07_grid_remaining_challenge.png`：主簡報，Grid and Periodic Structures，PSNR 差異 +0.01 dB。
- `internal_qc\08_internal_combo_better_edge_case.png`：內部備用，Minority Counterexample，PSNR 差異 -0.80 dB。

## 建議使用方式

- 對外或正式簡報：優先使用 `ppt_ready/00` 到 `ppt_ready/06`，展示 a025 在缺陷、大區塊、曲線、混合場景與紋理上的改善。
- 需要誠實說明限制時：使用 `ppt_ready/07_grid_remaining_challenge.png`，說明格線/週期結構仍是後續強化方向。
- 內部問答或風險討論：使用 `internal_qc/08_internal_combo_better_edge_case.png`，說明 a025 不是每張都勝過 COMBO。
