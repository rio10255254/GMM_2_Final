# a025 ONNX 多類顯微重建與外部 GMF 準備報告

- 模型包：`Deliverables/Company_Packages/GeoEdge_R39R40_a025_ONNX_Company_Package_20260511`
- 輸出根目錄：`Deliverables/Company_Packages/GeoEdge_R39R40_a025_ONNX_Company_Package_20260511/outputs/a025_multitype_microscopy_and_gmf_20260513`
- 顯微/邊界/位移抽樣重建張數：`387`

## 分類摘要

| dataset | family | count | PSNR | SSIM | ΔPSNR vs input | gradient retention | lap retention |
|---|---|---:|---:|---:|---:|---:|---:|
| r40_micro_val_unseen | edge_defects | 20 | 27.8415 | 0.9390 | 0.6185 | 0.8878 | 0.4487 |
| r40_micro_val_unseen | large_regions | 20 | 27.0950 | 0.9449 | -0.5122 | 1.0281 | 0.5007 |
| r40_micro_val_unseen | lines_grid | 20 | 18.5543 | 0.6326 | 0.3343 | 0.3139 | 0.1570 |
| r40_micro_val_unseen | mixed_fields | 20 | 24.7802 | 0.5474 | 0.2182 | 0.2233 | 0.3770 |
| r40_micro_val_unseen | textures | 20 | 28.7273 | 0.8956 | -3.1783 | 0.7646 | 0.4307 |
| r42_boundary_val_unseen | curves | 20 | 22.2151 | 0.7925 | -8.2120 | 1.0255 | 0.4894 |
| r42_boundary_val_unseen | defects | 20 | 26.2267 | 0.9196 | -5.6705 | 1.4842 | 0.5902 |
| r42_boundary_val_unseen | grids | 20 | 16.9018 | 0.5593 | -2.7044 | 0.4011 | 0.1164 |
| r42_boundary_val_unseen | junctions | 20 | 21.7035 | 0.8311 | -5.8485 | 0.9017 | 0.4561 |
| r42_boundary_val_unseen | large_regions | 20 | 26.3632 | 0.9122 | -6.3152 | 1.5874 | 0.5756 |
| r42_boundary_val_unseen | mixed_fields | 20 | 25.7222 | 0.8938 | -6.0193 | 1.4491 | 0.5399 |
| r42_boundary_val_unseen | thin_lines | 20 | 22.9548 | 0.8930 | -4.8102 | 0.9156 | 0.4781 |
| r44_motion_val_unseen_subset | curves | 21 | 24.2348 | 0.8371 | -6.6998 | 0.9213 | 0.4478 |
| r44_motion_val_unseen_subset | defects | 21 | 26.4351 | 0.9122 | -5.1315 | 1.3493 | 0.5701 |
| r44_motion_val_unseen_subset | grids | 21 | 15.3753 | 0.5709 | -4.1971 | 0.5344 | 0.2192 |
| r44_motion_val_unseen_subset | junctions | 21 | 22.5897 | 0.8902 | -5.1699 | 0.8277 | 0.4391 |
| r44_motion_val_unseen_subset | large_regions | 21 | 25.5557 | 0.8594 | -9.2275 | 1.7610 | 0.6281 |
| r44_motion_val_unseen_subset | mixed_fields | 21 | 26.3976 | 0.9096 | -6.5925 | 1.4232 | 0.5986 |
| r44_motion_val_unseen_subset | thin_lines | 21 | 23.5858 | 0.8708 | -5.1090 | 0.9512 | 0.5383 |

## 外部 GMF 準備路徑

- pitch8px：重建圖 `Deliverables/Company_Packages/GeoEdge_R39R40_a025_ONNX_Company_Package_20260511/outputs/a025_multitype_microscopy_and_gmf_20260513/external_gmf_prepare/recon_for_gmf/pitch8px`；GMF_score 放置 `Deliverables/Company_Packages/GeoEdge_R39R40_a025_ONNX_Company_Package_20260511/outputs/a025_multitype_microscopy_and_gmf_20260513/external_gmf_prepare/gmf_score_drop_here/pitch8px/GMF_score.txt`；張數 `101/101`
- pitch0p8px：重建圖 `Deliverables/Company_Packages/GeoEdge_R39R40_a025_ONNX_Company_Package_20260511/outputs/a025_multitype_microscopy_and_gmf_20260513/external_gmf_prepare/recon_for_gmf/pitch0p8px`；GMF_score 放置 `Deliverables/Company_Packages/GeoEdge_R39R40_a025_ONNX_Company_Package_20260511/outputs/a025_multitype_microscopy_and_gmf_20260513/external_gmf_prepare/gmf_score_drop_here/pitch0p8px/GMF_score.txt`；張數 `61/61`
- pitch0p08px：重建圖 `Deliverables/Company_Packages/GeoEdge_R39R40_a025_ONNX_Company_Package_20260511/outputs/a025_multitype_microscopy_and_gmf_20260513/external_gmf_prepare/recon_for_gmf/pitch0p08px`；GMF_score 放置 `Deliverables/Company_Packages/GeoEdge_R39R40_a025_ONNX_Company_Package_20260511/outputs/a025_multitype_microscopy_and_gmf_20260513/external_gmf_prepare/gmf_score_drop_here/pitch0p08px/GMF_score.txt`；張數 `41/41`
