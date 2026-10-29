# L0 Noise Floor 分析報告

- 生成時間:2026-05-15 02:58:02
- Trials:15
- FOV 點數:9(file indices = [13, 14, 17, 73, 74, 77, 93, 94, 97])
- Zernike + AC 維度:15
- Git commit:fcc30de8e97b
- Git branch:sandbox/r45
- MATLAB:25.2.0.3150157 (R2025b) Update 4

## 主結論

- **FOV 一致性良好**(max/min = 1.15,< 2)。後續 Test 1 可以用 **單一 global noise floor**,不需 per-FOV 校準。
- **全係數噪聲偏大**(中位 std = 0.04255,> 0.02);但要記住這個數字含 lock/bound/dead artifact,看下方乾淨版本。
- **乾淨 noise floor**(只算 7 個可信係數):中位 std = 0.02302
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
| x1 → Z2 Y-tilt (locked=0) | ✗ locked | 19% | 0.21462 | lock_tilt=true 強制 Z(2)/Z(3)=0,對 loss 無影響;BADS 隨便擲值 |
| x2 → Z3 X-tilt (locked=0) | ✗ locked | 19% | 0.19905 | lock_tilt=true 強制 Z(2)/Z(3)=0,對 loss 無影響;BADS 隨便擲值 |
| x3 → Z4 astig 45° (sin 2φ) | ✓ trustworthy | 4% | 0.04901 | std=±0.04949,在 search bounds 內部(撞邊 4%) |
| x4 → Z5 defocus | ✓ trustworthy | 27% | 0.32152 | std=±0.31962,在 search bounds 內部(撞邊 27%) |
| x5 → Z6 astig 0° (cos 2φ) | ✗ bound_saturated | 100% | 0.10328 | 100% 的值撞 search bounds [-0.100, +0.100];噪聲是「隨機選撞哪邊」,非真實演算法噪聲 |
| x6 → Z7 trefoil (sin 3φ) | ✗ bound_saturated | 96% | 0.03610 | 96% 的值撞 search bounds [-0.050, +0.050];噪聲是「隨機選撞哪邊」,非真實演算法噪聲 |
| x7 → Z8 coma Y (sin φ) | ✓ trustworthy | 0% | 0.02212 | std=±0.03138,在 search bounds 內部(撞邊 0%) |
| x8 → Z9 coma X (cos φ) | ✓ trustworthy | 53% | 0.00973 | std=±0.01519,在 search bounds 內部(撞邊 53%) |
| x9 → Z10 trefoil (cos 3φ) | ✗ bound_saturated | 99% | 0.05146 | 99% 的值撞 search bounds [-0.050, +0.050];噪聲是「隨機選撞哪邊」,非真實演算法噪聲 |
| x10 → Z11 quadrafoil (sin 4φ) | ✓ trustworthy | 22% | 0.00762 | std=±0.00755,在 search bounds 內部(撞邊 22%) |
| x11 → Z12 sec astig (sin 2φ) | ✓ trustworthy | 34% | 0.00774 | std=±0.00773,在 search bounds 內部(撞邊 34%) |
| x12 → Z13 spherical | ✓ trustworthy | 52% | 0.11098 | std=±0.11179,在 search bounds 內部(撞邊 52%) |
| x13 → Z14 sec astig (cos 2φ) | ✗ bound_saturated | 100% | 0.01033 | 100% 的值撞 search bounds [-0.010, +0.010];噪聲是「隨機選撞哪邊」,非真實演算法噪聲 |
| x14 → Z15 quadrafoil (cos 4φ) | ✗ bound_saturated | 91% | 0.00823 | 91% 的值撞 search bounds [-0.010, +0.010];噪聲是「隨機選撞哪邊」,非真實演算法噪聲 |
| x15 → AC amplitude | ✗ dead | 100% | 0.00000 | 跨全部 trial × FOV 完全相同(std≈0);BADS 對此維度收斂得很死,沒有可量噪聲 |

## 各 Zernike 係數的 noise floor(跨 FOV 平均)

| 係數 | mean std | mean MAD | std rank |
|---|---|---|---|
| x1 → Z2 Y-tilt (locked=0) | 0.21462 | 0.14548 | #2 |
| x2 → Z3 X-tilt (locked=0) | 0.19905 | 0.14356 | #3 |
| x3 → Z4 astig 45° (sin 2φ) | 0.04901 | 0.02663 | #7 |
| x4 → Z5 defocus | 0.32152 | 0.02685 | #1 |
| x5 → Z6 astig 0° (cos 2φ) | 0.10328 | 0.00000 | #5 |
| x6 → Z7 trefoil (sin 3φ) | 0.03610 | 0.00204 | #8 |
| x7 → Z8 coma Y (sin φ) | 0.02212 | 0.00031 | #9 |
| x8 → Z9 coma X (cos φ) | 0.00973 | 0.00003 | #11 |
| x9 → Z10 trefoil (cos 3φ) | 0.05146 | 0.00024 | #6 |
| x10 → Z11 quadrafoil (sin 4φ) | 0.00762 | 0.00571 | #14 |
| x11 → Z12 sec astig (sin 2φ) | 0.00774 | 0.00502 | #13 |
| x12 → Z13 spherical | 0.11098 | 0.00806 | #4 |
| x13 → Z14 sec astig (cos 2φ) | 0.01033 | 0.00000 | #10 |
| x14 → Z15 quadrafoil (cos 4φ) | 0.00823 | 0.00000 | #12 |
| x15 → AC amplitude | 0.00000 | 0.00000 | #15 |

## 各 FOV 點的 noise floor(跨 Zernike 平均)

| FOV | mean std |
|---|---|
| #13 (row 2, col 3) | 0.07755 |
| #14 (row 2, col 4) | 0.07608 |
| #17 (row 2, col 7) | 0.07456 |
| #73 (row 8, col 3) | 0.08022 |
| #74 (row 8, col 4) | 0.07912 |
| #77 (row 8, col 7) | 0.07036 |
| #93 (row 10, col 3) | 0.07663 |
| #94 (row 10, col 4) | 0.07591 |
| #97 (row 10, col 7) | 0.08064 |

## 完整 std 矩陣 (Zernike × FOV)

| 係數 \ FOV | #13 | #14 | #17 | #73 | #74 | #77 | #93 | #94 | #97 |
|---|---|---|---|---|---|---|---|---|---|
| x1 → Z2 Y-tilt (locked=0) | 0.17763 | 0.21850 | 0.23248 | 0.24211 | 0.22154 | 0.17695 | 0.19057 | 0.22331 | 0.24853 |
| x2 → Z3 X-tilt (locked=0) | 0.22905 | 0.18540 | 0.16030 | 0.23163 | 0.21713 | 0.13151 | 0.20184 | 0.20511 | 0.22944 |
| x3 → Z4 astig 45° (sin 2φ) | 0.05865 | 0.05645 | 0.04913 | 0.04965 | 0.05169 | 0.04825 | 0.03780 | 0.04058 | 0.04884 |
| x4 → Z5 defocus | 0.30871 | 0.28351 | 0.29816 | 0.32497 | 0.33249 | 0.33233 | 0.36252 | 0.32464 | 0.32638 |
| x5 → Z6 astig 0° (cos 2φ) | 0.10328 | 0.10328 | 0.10328 | 0.10328 | 0.10328 | 0.10328 | 0.10328 | 0.10328 | 0.10328 |
| x6 → Z7 trefoil (sin 3φ) | 0.05071 | 0.05071 | 0.01836 | 0.05139 | 0.05164 | 0.05162 | 0.00001 | 0.05044 | 0.00005 |
| x7 → Z8 coma Y (sin φ) | 0.00392 | 0.01677 | 0.03167 | 0.01995 | 0.01997 | 0.00020 | 0.04543 | 0.01799 | 0.04318 |
| x8 → Z9 coma X (cos φ) | 0.02300 | 0.02304 | 0.02302 | 0.00000 | 0.01160 | 0.00678 | 0.00000 | 0.00008 | 0.00000 |
| x9 → Z10 trefoil (cos 3φ) | 0.05164 | 0.05164 | 0.05163 | 0.05146 | 0.05163 | 0.05163 | 0.05071 | 0.05157 | 0.05122 |
| x10 → Z11 quadrafoil (sin 4φ) | 0.00722 | 0.00831 | 0.00784 | 0.00717 | 0.00690 | 0.00822 | 0.00729 | 0.00748 | 0.00810 |
| x11 → Z12 sec astig (sin 2φ) | 0.00659 | 0.00778 | 0.00810 | 0.00782 | 0.00698 | 0.00801 | 0.00712 | 0.00860 | 0.00871 |
| x12 → Z13 spherical | 0.12421 | 0.11729 | 0.11599 | 0.09536 | 0.09329 | 0.11811 | 0.12421 | 0.08712 | 0.12322 |
| x13 → Z14 sec astig (cos 2φ) | 0.01033 | 0.01033 | 0.01033 | 0.01033 | 0.01033 | 0.01033 | 0.01033 | 0.01033 | 0.01033 |
| x14 → Z15 quadrafoil (cos 4φ) | 0.00828 | 0.00826 | 0.00806 | 0.00820 | 0.00828 | 0.00823 | 0.00828 | 0.00822 | 0.00825 |
| x15 → AC amplitude | 0.00000 | 0.00000 | 0.00000 | 0.00000 | 0.00000 | 0.00000 | 0.00000 | 0.00000 | 0.00000 |

## 後續行動建議

1. 把 `noise_floor.json`(本目錄旁邊)當成 Test 1 z-score 的分母 (`noise_floor_std`)。
2. 之後 L1 (重拍 100 張) 跑完後,跨 trial 算同樣 std,跟本 L0 結果相減即得「拍攝噪聲淨貢獻」。
3. 若 `std rank` 顯示高階模態 (Z11–Z15) 的 std 顯著大於低階,需重看 DESIGN §7.5.1 的「可解釋模態」清單。
4. 若 FOV 一致性差,L1 之後的層也要用 per-FOV noise floor,不能合併成單一數字。

## 用到的 trial 目錄

- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setD/outputs/trial_01`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setD/outputs/trial_02`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setD/outputs/trial_03`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setD/outputs/trial_04`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setD/outputs/trial_05`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setD/outputs/trial_06`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setD/outputs/trial_07`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setD/outputs/trial_08`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setD/outputs/trial_09`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setD/outputs/trial_10`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setD/outputs/trial_11`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setD/outputs/trial_12`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setD/outputs/trial_13`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setD/outputs/trial_14`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setD/outputs/trial_15`
