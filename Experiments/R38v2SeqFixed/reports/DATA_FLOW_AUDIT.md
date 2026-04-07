# R38v2 資料流審計

**日期**: 2026-04-07

## 三條資料流

### 流 1：Main Training（single-crop）
```
src: Training_Data/tra_src_ring/ (1100 files, 6001-7100.bmp, 512×512 uint8)
lbl: Training_Data/tra_lbl_ring/ (1100 files, 6001-7100.bmp, 512×512 uint8)
```
- 生成日期：2025-12-16
- PSF 版本：**未知舊版**（不在 generated/ 的 1-2468 範圍，非 Data_Simulaion.py 產出）
- 這批資料從 R30 起就被用於所有訓練

### 流 2：Sequence Training（R38v2 新增）
```
src: Training_Data/generated_convolved/stage_25,26/ (150 files, uint16 TIFF)
lbl: Training_Data/generated/stage_25,26/ (150 files, uint16 TIFF)
```
- 卷積日期：2026-04-06（用新 PSF 重新卷積，seed=42）
- 乾淨影像生成：2026-03-11（Data_Simulaion.py）
- PSF 版本：**新 Whole-FOV PSF**（2026-03-25）
- 舊版備份：`Training_Data/_backup_old_psf_convolved_seq/`

### 流 3：Model Physics Layer
```
PSF: PSF_Fitting/Crop_circle_FreqFiltered/Fits/PSF_fitted_2D_FOVstack.mat
```
- 版本：新 Whole-FOV PSF（2026-03-25）
- 載入：訓練 init 時讀入 model buffer

## PSF 一致性矩陣

| 元件 | PSF 版本 | 備註 |
|------|---------|------|
| tra_src_ring（main src） | 舊版（2025-12） | 從 R30 起共用 |
| generated_convolved（seq src） | 新版（2026-04-06） | R38v2 重新卷積 |
| Model physics layer | 新版（2026-03-25） | runtime default |
| NTU test images | 真實光學 | — |

## 已知風險

1. **Main training data 和 model PSF 不一致**：tra_src_ring 用舊 PSF，model 載新 PSF。此不一致從 R30 就存在，非 R38v2 引入。Pure PSF Control 驗證新舊差異小。
2. **R38v2 同一訓練混合兩種 PSF 的資料**：main (舊 PSF) + seq (新 PSF)。但 seq loss 只比較幀間 delta，不直接比較像素值，PSF 差異的影響有限。
3. **tra_src_ring 來源不明**：ID 6001-7100 不在 generated/ 範圍，可能是早期獨立資料集。

## 建議

- **短期**：問題不影響已驗證的外部 GMF 結果（R33/R38v2 都 PASS）
- **長期（架構重構時）**：用新 PSF 重新生成完整訓練資料集（tra_src_ring 的替代品），確保全鏈一致
