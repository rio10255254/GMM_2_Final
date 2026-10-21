# V42 Training-data representative images

The 15 BMP files in this folder are representative source images selected from the active V42 training package. The files are copied without changing their pixel values.

## Recommended main-slide set

For the main presentation, use items 03, 04, 05, 06, 08, 09, 12, and 15. The remaining items are best kept for an appendix because several motion subsets are visually similar.

## Bilingual captions

| No. | File | 中文說明 | English description |
|---:|---|---|---|
| 1 | `01_legacy_shape.bmp` | 基礎形狀資料：包含環形、圓形與其他基本幾何結構，用於建立模型對形狀與邊界的基本辨識能力。 | **Basic shape pairs:** Contains annular, circular, and other basic geometries to establish the model's basic understanding of shape and boundary location. |
| 2 | `02_sequence_guard_hs100mg_pillar.bmp` | 序列穩定資料：以規則 pillar 序列建立相鄰影格的結構與位置基準，降低連續影像中的位置漂移。 | **Sequence-consistency guard:** Uses ordered pillar sequences to define structural and positional consistency across frames, reducing output drift in sequential images. |
| 3 | `03_sem_reference_geometry_real_pillar.bmp` | SEM 參考幾何資料：將真實樣品影像與 SEM 參考幾何配對，提供 pillar 邊界與尺寸的獨立幾何依據。 | **SEM-anchored geometry:** Pairs real sample images with SEM reference geometry, providing an independent geometric reference for pillar boundaries and size. |
| 4 | `04_universal_synthetic_annulus.bmp` | 通用合成幾何資料：使用多種形狀與亮暗條件，擴充模型對幾何和對比變化的適應性。 | **Universal synthetic shapes:** Uses multiple geometries and polarity conditions to broaden robustness to shape and contrast changes. |
| 5 | `05_motion_synthetic_ellipse.bmp` | 合成位移資料：在已知幾何影像中加入可控位移，建立精確的位移學習參考。 | **Synthetic motion pairs:** Applies controlled shifts to known geometries to provide an exact reference for displacement learning. |
| 6 | `06_real_texture_motion_ellipse.bmp` | 真實紋理位移資料：在真實顯微紋理上加入已知位移，同時保留真實雜訊與光學背景。 | **Real-texture motion pairs:** Applies known shifts to real microscope textures so the model learns realistic noise together with positional change. |
| 7 | `07_step_guard_motion_texture_ellipse.bmp` | 步距防護資料：使用受控位移步距與真實紋理，避免模型將位移大小或方向學錯。 | **Step-guard motion pairs:** Uses controlled displacement steps with real textures to prevent incorrect shift magnitude or direction. |
| 8 | `08_target_real_pseudo_mixed_pillar_line.bmp` | 真實目標資料：加入實際樣品的 pillar、線寬與背景區域，並以教師參考邊界提供真實影像域監督。 | **Target-domain real images:** Adds real target-domain pillar, line-width, and background regions, using teacher-reference boundaries for supervision in the real image domain. |
| 9 | `09_target_real_motion_pair_20x.bmp` | 真實位移配對：來自實際位移序列，保留真實光學變化與平台移動資訊，用於學習連續影格穩定性。 | **Real experimental motion pairs:** Derived from measured displacement sequences, preserving real optical changes and stage-motion information for sequential stability. |
| 10 | `10_target_selfshift_100mg_mixed.bmp` | 真實影像自位移資料：以真實目標紋理建立精確自位移配對，強化重建前後的結構位置對應。 | **Real-texture self-shift pairs:** Creates exact self-shift pairs from real target textures to strengthen positional correspondence between reconstructed images. |
| 11 | `11_gmf_roi_selfshift_20x.bmp` | GMF ROI 自位移資料：聚焦於局部高密度結構，提供較具挑戰性的位移訓練樣本。 | **GMF ROI self-shift pairs:** Focuses on localized, high-density structures to provide challenging motion-training samples. |
| 12 | `12_lowmag_gmf_dot_5x.bmp` | 低倍率點陣資料：加入 5× 低倍率點陣影像，補足較大視野與較低解析度條件。 | **Low-magnification dot/GMF regions:** Adds 5× dot-array images to cover larger fields of view and lower-resolution conditions. |
| 13 | `13_lowmag_square_shape_5x.bmp` | 低倍率方形與線寬資料：涵蓋不同形貌與尺度，擴充模型的結構適應能力。 | **Low-magnification square/line regions:** Covers different geometries and scales to broaden structural adaptation. |
| 14 | `14_multimag_motion_guard_20x.bmp` | 多倍率位移防護資料：混合 20× 與 5× 實驗域，維持倍率改變後的位置一致性。 | **Multi-magnification motion guard:** Combines 20× and 5× experimental domains to preserve positional consistency across magnifications. |
| 15 | `15_stability_shape_teacher_100mg.bmp` | 穩定形狀教師資料：以形狀穩定教師標籤約束輸出輪廓，降低邊界晃動與形狀變形。 | **Stability-shape teacher pairs:** Uses stability-shape teacher labels to constrain contours and reduce boundary jitter and shape deformation. |

## Data structure

```text
V42_SoftLabelSNR_FullStandalone_20260709/
├─ train_v42.py                         training entry point
├─ training_data/
│  ├─ manifest.json                     source and role record
│  ├─ src/                              input images
│  │  ├─ stage_34_...                   basic/legacy shapes
│  │  ├─ stage_35_...                   sequence guard
│  │  ├─ stage_36_...                   SEM reference geometry
│  │  ├─ stage_37_...                   universal synthetic shapes
│  │  ├─ stage_38_...                   synthetic motion
│  │  ├─ stage_39_...                   real-texture motion
│  │  └─ stage_40_...                   step guard and real-target groups
│  ├─ lbl/                              paired target/teacher labels
│  ├─ geom/
│  │  ├─ boundary/                      boundary maps
│  │  ├─ centerline/                    centerline maps
│  │  ├─ distance/                      distance maps
│  │  └─ meta/                          geometry/source metadata
│  └─ splits/                            fixed grouped train/validation splits
├─ psf/                                  fixed optical prior
├─ weights/                              model checkpoints
└─ results/                              training outputs
```

The package contains 11,254 active source-label pairs. The loader uses a 256-pixel crop size; some source files are stored as 512 × 512 images and are randomly cropped to 256 × 256 during training.
