# a025 ONNX vs COMBO ONNX 顯微影像重建比較

- COMBO 包：`Deliverables/Company_Packages/GeoEdge_COMBO_ONNX_Company_Package_20260424`
- a025 包：`Deliverables/Company_Packages/GeoEdge_R39R40_a025_ONNX_Company_Package_20260511`
- 比較輸出根目錄：`Deliverables/Company_Packages/GeoEdge_R39R40_a025_ONNX_Company_Package_20260511/outputs/a025_vs_combo_onnx_microscopy_compare_20260513`
- 比較張數：`387`

## 整體結果

| count | COMBO PSNR | a025 PSNR | a025-COMBO | COMBO SSIM | a025 SSIM | a025 勝率 |
|---:|---:|---:|---:|---:|---:|---:|
| 387 | 21.2667 | 23.8485 | +2.5817 | 0.7714 | 0.8219 | 99.0% |

## 分資料集結果

| dataset | count | COMBO PSNR | a025 PSNR | a025-COMBO | a025 勝率 |
|---|---:|---:|---:|---:|---:|
| r40_micro_val_unseen | 100 | 22.7241 | 25.3996 | +2.6755 | 100.0% |
| r42_boundary_val_unseen | 140 | 20.5425 | 23.1553 | +2.6128 | 97.1% |
| r44_motion_val_unseen_subset | 147 | 20.9651 | 23.4534 | +2.4883 | 100.0% |

## 分類結果

| dataset | family | count | COMBO PSNR | a025 PSNR | a025-COMBO | a025 勝率 | 梯度保留差 |
|---|---|---:|---:|---:|---:|---:|---:|
| r40_micro_val_unseen | edge_defects | 20 | 23.8491 | 27.8415 | +3.9924 | 100.0% | -0.1812 |
| r40_micro_val_unseen | large_regions | 20 | 23.1292 | 27.0950 | +3.9658 | 100.0% | -0.1728 |
| r40_micro_val_unseen | lines_grid | 20 | 17.7053 | 18.5543 | +0.8490 | 100.0% | +0.0862 |
| r40_micro_val_unseen | mixed_fields | 20 | 21.8800 | 24.7802 | +2.9002 | 100.0% | -0.0059 |
| r40_micro_val_unseen | textures | 20 | 27.0568 | 28.7273 | +1.6704 | 100.0% | +0.1870 |
| r42_boundary_val_unseen | curves | 20 | 19.2183 | 22.2151 | +2.9968 | 100.0% | +0.1998 |
| r42_boundary_val_unseen | defects | 20 | 23.1869 | 26.2267 | +3.0398 | 95.0% | +0.2727 |
| r42_boundary_val_unseen | grids | 20 | 16.4379 | 16.9018 | +0.4639 | 95.0% | +0.0889 |
| r42_boundary_val_unseen | junctions | 20 | 18.9559 | 21.7035 | +2.7475 | 100.0% | +0.2017 |
| r42_boundary_val_unseen | large_regions | 20 | 23.2159 | 26.3632 | +3.1473 | 90.0% | +0.2676 |
| r42_boundary_val_unseen | mixed_fields | 20 | 22.5969 | 25.7222 | +3.1253 | 100.0% | +0.2336 |
| r42_boundary_val_unseen | thin_lines | 20 | 20.1856 | 22.9548 | +2.7692 | 100.0% | +0.1900 |
| r44_motion_val_unseen_subset | curves | 21 | 21.1832 | 24.2348 | +3.0517 | 100.0% | +0.1122 |
| r44_motion_val_unseen_subset | defects | 21 | 23.1576 | 26.4351 | +3.2775 | 100.0% | +0.2818 |
| r44_motion_val_unseen_subset | grids | 21 | 14.5809 | 15.3753 | +0.7944 | 100.0% | +0.1360 |
| r44_motion_val_unseen_subset | junctions | 21 | 19.8510 | 22.5897 | +2.7387 | 100.0% | +0.1838 |
| r44_motion_val_unseen_subset | large_regions | 21 | 23.2280 | 25.5557 | +2.3276 | 100.0% | +0.2111 |
| r44_motion_val_unseen_subset | mixed_fields | 21 | 23.9635 | 26.3976 | +2.4341 | 100.0% | +0.2901 |
| r44_motion_val_unseen_subset | thin_lines | 21 | 20.7915 | 23.5858 | +2.7943 | 100.0% | +0.1795 |

## 視覺對照圖

- 分類代表圖：`Deliverables/Company_Packages/GeoEdge_R39R40_a025_ONNX_Company_Package_20260511/outputs/a025_vs_combo_onnx_microscopy_compare_20260513/visuals/a025_vs_combo_representative_by_family.png`
- a025 贏最多的案例：`Deliverables/Company_Packages/GeoEdge_R39R40_a025_ONNX_Company_Package_20260511/outputs/a025_vs_combo_onnx_microscopy_compare_20260513/visuals/a025_biggest_wins_vs_combo.png`
- COMBO 贏最多的案例：`Deliverables/Company_Packages/GeoEdge_R39R40_a025_ONNX_Company_Package_20260511/outputs/a025_vs_combo_onnx_microscopy_compare_20260513/visuals/combo_biggest_wins_vs_a025.png`

## 檔案

- 每張圖詳細數字：`Deliverables/Company_Packages/GeoEdge_R39R40_a025_ONNX_Company_Package_20260511/outputs/a025_vs_combo_onnx_microscopy_compare_20260513/metrics/a025_vs_combo_per_image.csv`
- 分類摘要：`Deliverables/Company_Packages/GeoEdge_R39R40_a025_ONNX_Company_Package_20260511/outputs/a025_vs_combo_onnx_microscopy_compare_20260513/metrics/a025_vs_combo_family_summary.csv`
- JSON 摘要：`Deliverables/Company_Packages/GeoEdge_R39R40_a025_ONNX_Company_Package_20260511/outputs/a025_vs_combo_onnx_microscopy_compare_20260513/metrics/a025_vs_combo_summary.json`
