# L0 Noise Floor 分析報告

- 生成時間:2026-05-15 01:26:07
- Trials:15
- FOV 點數:9(file indices = [30, 33, 37, 60, 63, 67, 80, 83, 87])
- Zernike + AC 維度:15
- Git commit:fcc30de8e97b
- Git branch:sandbox/r45
- MATLAB:25.2.0.3150157 (R2025b) Update 4

## 主結論

- **FOV 一致性良好**(max/min = 1.11,< 2)。後續 Test 1 可以用 **單一 global noise floor**,不需 per-FOV 校準。
- **全係數噪聲偏大**(中位 std = 0.02446,> 0.02);但要記住這個數字含 lock/bound/dead artifact,看下方乾淨版本。
- **乾淨 noise floor**(只算 7 個可信係數):中位 std = 0.02247
  - 這個數字才是真正的「BADS 演算法在收斂域內的隨機性」量級
  - 後續 attribution Test 1 的 z-score 分母應該用這個,而不是含 artifact 的全係數版本

## 係數可信度分類

BADS 對不同係數的行為差很多——有些是真的有噪聲可量,有些是 artifact。
分類規則:
- `locked`: lock_tilt 強制鎖 0,對 loss 沒影響(BADS 隨便擲)
- `bound_saturated`: > 80% 的值撞 search bounds (噪聲是「隨機選撞哪邊」)
- `dead`: 跨全部 trial × FOV 完全相同(BADS 收斂得很死)
- `trustworthy`: 在 search bounds 內部,有真實抖動可量

| 係數 | 分類 | 撞邊 % | 跨 trial std (mean) | 原因 |
|---|---|---|---|---|
| x1 → Z2 Y-tilt (locked=0) | ✗ locked | 18% | 0.21153 | lock_tilt=true 強制 Z(2)/Z(3)=0,對 loss 無影響;BADS 隨便擲值 |
| x2 → Z3 X-tilt (locked=0) | ✗ locked | 18% | 0.20042 | lock_tilt=true 強制 Z(2)/Z(3)=0,對 loss 無影響;BADS 隨便擲值 |
| x3 → Z4 astig 45° (sin 2φ) | ✓ trustworthy | 3% | 0.04105 | std=±0.04120,在 search bounds 內部(撞邊 3%) |
| x4 → Z5 defocus | ✓ trustworthy | 24% | 0.32851 | std=±0.32449,在 search bounds 內部(撞邊 24%) |
| x5 → Z6 astig 0° (cos 2φ) | ✗ bound_saturated | 100% | 0.05164 | 100% 的值撞 search bounds [-0.100, +0.100];噪聲是「隨機選撞哪邊」,非真實演算法噪聲 |
| x6 → Z7 trefoil (sin 3φ) | ✗ bound_saturated | 99% | 0.01747 | 99% 的值撞 search bounds [-0.050, +0.050];噪聲是「隨機選撞哪邊」,非真實演算法噪聲 |
| x7 → Z8 coma Y (sin φ) | ✓ trustworthy | 1% | 0.01905 | std=±0.02148,在 search bounds 內部(撞邊 1%) |
| x8 → Z9 coma X (cos φ) | ✓ trustworthy | 53% | 0.00259 | std=±0.01113,在 search bounds 內部(撞邊 53%) |
| x9 → Z10 trefoil (cos 3φ) | ✗ bound_saturated | 98% | 0.02987 | 98% 的值撞 search bounds [-0.050, +0.050];噪聲是「隨機選撞哪邊」,非真實演算法噪聲 |
| x10 → Z11 quadrafoil (sin 4φ) | ✓ trustworthy | 17% | 0.00642 | std=±0.00665,在 search bounds 內部(撞邊 17%) |
| x11 → Z12 sec astig (sin 2φ) | ✓ trustworthy | 22% | 0.00659 | std=±0.00669,在 search bounds 內部(撞邊 22%) |
| x12 → Z13 spherical | ✓ trustworthy | 59% | 0.11252 | std=±0.11289,在 search bounds 內部(撞邊 59%) |
| x13 → Z14 sec astig (cos 2φ) | ✗ bound_saturated | 100% | 0.00516 | 100% 的值撞 search bounds [-0.010, +0.010];噪聲是「隨機選撞哪邊」,非真實演算法噪聲 |
| x14 → Z15 quadrafoil (cos 4φ) | ✗ bound_saturated | 90% | 0.00823 | 90% 的值撞 search bounds [-0.010, +0.010];噪聲是「隨機選撞哪邊」,非真實演算法噪聲 |
| x15 → AC amplitude | ✗ dead | 100% | 0.00000 | 跨全部 trial × FOV 完全相同(std≈0);BADS 對此維度收斂得很死,沒有可量噪聲 |

## 各 Zernike 係數的 noise floor(跨 FOV 平均)

| 係數 | mean std | mean MAD | std rank |
|---|---|---|---|
| x1 → Z2 Y-tilt (locked=0) | 0.21153 | 0.16611 | #2 |
| x2 → Z3 X-tilt (locked=0) | 0.20042 | 0.11077 | #3 |
| x3 → Z4 astig 45° (sin 2φ) | 0.04105 | 0.02768 | #6 |
| x4 → Z5 defocus | 0.32851 | 0.02025 | #1 |
| x5 → Z6 astig 0° (cos 2φ) | 0.05164 | 0.00000 | #5 |
| x6 → Z7 trefoil (sin 3φ) | 0.01747 | 0.00000 | #9 |
| x7 → Z8 coma Y (sin φ) | 0.01905 | 0.00001 | #8 |
| x8 → Z9 coma X (cos φ) | 0.00259 | 0.00002 | #14 |
| x9 → Z10 trefoil (cos 3φ) | 0.02987 | 0.00000 | #7 |
| x10 → Z11 quadrafoil (sin 4φ) | 0.00642 | 0.00479 | #12 |
| x11 → Z12 sec astig (sin 2φ) | 0.00659 | 0.00512 | #11 |
| x12 → Z13 spherical | 0.11252 | 0.00554 | #4 |
| x13 → Z14 sec astig (cos 2φ) | 0.00516 | 0.00000 | #13 |
| x14 → Z15 quadrafoil (cos 4φ) | 0.00823 | 0.00008 | #10 |
| x15 → AC amplitude | 0.00000 | 0.00000 | #15 |

## 各 FOV 點的 noise floor(跨 Zernike 平均)

| FOV | mean std |
|---|---|
| #30 (row 3, col 10) | 0.07035 |
| #33 (row 4, col 3) | 0.07117 |
| #37 (row 4, col 7) | 0.07261 |
| #60 (row 6, col 10) | 0.06658 |
| #63 (row 7, col 3) | 0.06737 |
| #67 (row 7, col 7) | 0.07267 |
| #80 (row 8, col 10) | 0.06881 |
| #83 (row 9, col 3) | 0.06932 |
| #87 (row 9, col 7) | 0.06576 |

## 完整 std 矩陣 (Zernike × FOV)

| 係數 \ FOV | #30 | #33 | #37 | #60 | #63 | #67 | #80 | #83 | #87 |
|---|---|---|---|---|---|---|---|---|---|
| x1 → Z2 Y-tilt (locked=0) | 0.20911 | 0.24057 | 0.24965 | 0.23124 | 0.23576 | 0.18292 | 0.16428 | 0.21395 | 0.17630 |
| x2 → Z3 X-tilt (locked=0) | 0.17619 | 0.21365 | 0.20205 | 0.18670 | 0.20257 | 0.23498 | 0.20743 | 0.19717 | 0.18305 |
| x3 → Z4 astig 45° (sin 2φ) | 0.03486 | 0.04307 | 0.04498 | 0.03371 | 0.03900 | 0.05658 | 0.05109 | 0.03382 | 0.03232 |
| x4 → Z5 defocus | 0.34491 | 0.32656 | 0.31144 | 0.28301 | 0.29792 | 0.35772 | 0.38113 | 0.32819 | 0.32568 |
| x5 → Z6 astig 0° (cos 2φ) | 0.05164 | 0.05164 | 0.05164 | 0.05164 | 0.05164 | 0.05164 | 0.05164 | 0.05164 | 0.05164 |
| x6 → Z7 trefoil (sin 3φ) | 0.04140 | 0.00013 | 0.03518 | 0.01298 | 0.00015 | 0.00000 | 0.00000 | 0.03222 | 0.03519 |
| x7 → Z8 coma Y (sin φ) | 0.00164 | 0.02998 | 0.01094 | 0.02247 | 0.02510 | 0.03110 | 0.02573 | 0.01308 | 0.01145 |
| x8 → Z9 coma X (cos φ) | 0.00822 | 0.00587 | 0.00002 | 0.00029 | 0.00050 | 0.00000 | 0.00000 | 0.00758 | 0.00080 |
| x9 → Z10 trefoil (cos 3φ) | 0.03519 | 0.03517 | 0.03519 | 0.03518 | 0.03502 | 0.02280 | 0.00000 | 0.03513 | 0.03519 |
| x10 → Z11 quadrafoil (sin 4φ) | 0.00743 | 0.00720 | 0.00632 | 0.00321 | 0.00692 | 0.00758 | 0.00698 | 0.00590 | 0.00625 |
| x11 → Z12 sec astig (sin 2φ) | 0.00703 | 0.00764 | 0.00628 | 0.00479 | 0.00718 | 0.00714 | 0.00628 | 0.00678 | 0.00620 |
| x12 → Z13 spherical | 0.12421 | 0.09271 | 0.12216 | 0.12002 | 0.09550 | 0.12421 | 0.12421 | 0.10085 | 0.10883 |
| x13 → Z14 sec astig (cos 2φ) | 0.00516 | 0.00516 | 0.00516 | 0.00516 | 0.00516 | 0.00516 | 0.00516 | 0.00516 | 0.00516 |
| x14 → Z15 quadrafoil (cos 4φ) | 0.00828 | 0.00819 | 0.00813 | 0.00827 | 0.00807 | 0.00828 | 0.00828 | 0.00828 | 0.00827 |
| x15 → AC amplitude | 0.00000 | 0.00000 | 0.00000 | 0.00000 | 0.00000 | 0.00000 | 0.00000 | 0.00000 | 0.00000 |

## 後續行動建議

1. 把 `noise_floor.json`(本目錄旁邊)當成 Test 1 z-score 的分母 (`noise_floor_std`)。
2. 之後 L1 (重拍 100 張) 跑完後,跨 trial 算同樣 std,跟本 L0 結果相減即得「拍攝噪聲淨貢獻」。
3. 若 `std rank` 顯示高階模態 (Z11–Z15) 的 std 顯著大於低階,需重看 DESIGN §7.5.1 的「可解釋模態」清單。
4. 若 FOV 一致性差,L1 之後的層也要用 per-FOV noise floor,不能合併成單一數字。

## 用到的 trial 目錄

- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit_setC\outputs\trial_01`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit_setC\outputs\trial_02`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit_setC\outputs\trial_03`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit_setC\outputs\trial_04`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit_setC\outputs\trial_05`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit_setC\outputs\trial_06`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit_setC\outputs\trial_07`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit_setC\outputs\trial_08`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit_setC\outputs\trial_09`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit_setC\outputs\trial_10`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit_setC\outputs\trial_11`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit_setC\outputs\trial_12`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit_setC\outputs\trial_13`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit_setC\outputs\trial_14`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit_setC\outputs\trial_15`
