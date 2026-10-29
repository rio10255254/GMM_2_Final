# L0 Noise Floor 分析報告

- 生成時間:2026-05-14 20:03:02
- Trials:15
- FOV 點數:9(file indices = [12, 16, 19, 52, 56, 59, 82, 86, 89])
- Zernike + AC 維度:15
- Git commit:fcc30de8e97b
- Git branch:sandbox/r45
- MATLAB:25.2.0.3150157 (R2025b) Update 4

## 主結論

- **FOV 一致性良好**(max/min = 1.14,< 2)。後續 Test 1 可以用 **單一 global noise floor**,不需 per-FOV 校準。
- **全係數噪聲偏大**(中位 std = 0.03795,> 0.02);但要記住這個數字含 lock/bound/dead artifact,看下方乾淨版本。
- **乾淨 noise floor**(只算 7 個可信係數):中位 std = 0.02732
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
| x1 → Z2 Y-tilt (locked=0) | ✗ locked | 20% | 0.22230 | lock_tilt=true 強制 Z(2)/Z(3)=0,對 loss 無影響;BADS 隨便擲值 |
| x2 → Z3 X-tilt (locked=0) | ✗ locked | 21% | 0.21913 | lock_tilt=true 強制 Z(2)/Z(3)=0,對 loss 無影響;BADS 隨便擲值 |
| x3 → Z4 astig 45° (sin 2φ) | ✓ trustworthy | 0% | 0.03958 | std=±0.04138,在 search bounds 內部(撞邊 0%) |
| x4 → Z5 defocus | ✓ trustworthy | 23% | 0.36907 | std=±0.36353,在 search bounds 內部(撞邊 23%) |
| x5 → Z6 astig 0° (cos 2φ) | ✗ bound_saturated | 100% | 0.10142 | 100% 的值撞 search bounds [-0.100, +0.100];噪聲是「隨機選撞哪邊」,非真實演算法噪聲 |
| x6 → Z7 trefoil (sin 3φ) | ✗ bound_saturated | 96% | 0.04050 | 96% 的值撞 search bounds [-0.050, +0.050];噪聲是「隨機選撞哪邊」,非真實演算法噪聲 |
| x7 → Z8 coma Y (sin φ) | ✓ trustworthy | 0% | 0.03045 | std=±0.03288,在 search bounds 內部(撞邊 0%) |
| x8 → Z9 coma X (cos φ) | ✓ trustworthy | 30% | 0.01089 | std=±0.01800,在 search bounds 內部(撞邊 30%) |
| x9 → Z10 trefoil (cos 3φ) | ✗ bound_saturated | 99% | 0.03632 | 99% 的值撞 search bounds [-0.050, +0.050];噪聲是「隨機選撞哪邊」,非真實演算法噪聲 |
| x10 → Z11 quadrafoil (sin 4φ) | ✓ trustworthy | 24% | 0.00734 | std=±0.00733,在 search bounds 內部(撞邊 24%) |
| x11 → Z12 sec astig (sin 2φ) | ✓ trustworthy | 27% | 0.00726 | std=±0.00723,在 search bounds 內部(撞邊 27%) |
| x12 → Z13 spherical | ✓ trustworthy | 48% | 0.12567 | std=±0.12442,在 search bounds 內部(撞邊 48%) |
| x13 → Z14 sec astig (cos 2φ) | ✗ bound_saturated | 100% | 0.01014 | 100% 的值撞 search bounds [-0.010, +0.010];噪聲是「隨機選撞哪邊」,非真實演算法噪聲 |
| x14 → Z15 quadrafoil (cos 4φ) | ✗ bound_saturated | 89% | 0.00957 | 89% 的值撞 search bounds [-0.010, +0.010];噪聲是「隨機選撞哪邊」,非真實演算法噪聲 |
| x15 → AC amplitude | ✗ dead | 100% | 0.00000 | 跨全部 trial × FOV 完全相同(std≈0);BADS 對此維度收斂得很死,沒有可量噪聲 |

## 各 Zernike 係數的 noise floor(跨 FOV 平均)

| 係數 | mean std | mean MAD | std rank |
|---|---|---|---|
| x1 → Z2 Y-tilt (locked=0) | 0.22230 | 0.19559 | #2 |
| x2 → Z3 X-tilt (locked=0) | 0.21913 | 0.16947 | #3 |
| x3 → Z4 astig 45° (sin 2φ) | 0.03958 | 0.02950 | #7 |
| x4 → Z5 defocus | 0.36907 | 0.05569 | #1 |
| x5 → Z6 astig 0° (cos 2φ) | 0.10142 | 0.00000 | #5 |
| x6 → Z7 trefoil (sin 3φ) | 0.04050 | 0.00000 | #6 |
| x7 → Z8 coma Y (sin φ) | 0.03045 | 0.00016 | #9 |
| x8 → Z9 coma X (cos φ) | 0.01089 | 0.00003 | #10 |
| x9 → Z10 trefoil (cos 3φ) | 0.03632 | 0.00000 | #8 |
| x10 → Z11 quadrafoil (sin 4φ) | 0.00734 | 0.00545 | #13 |
| x11 → Z12 sec astig (sin 2φ) | 0.00726 | 0.00592 | #14 |
| x12 → Z13 spherical | 0.12567 | 0.01570 | #4 |
| x13 → Z14 sec astig (cos 2φ) | 0.01014 | 0.00000 | #11 |
| x14 → Z15 quadrafoil (cos 4φ) | 0.00957 | 0.00011 | #12 |
| x15 → AC amplitude | 0.00000 | 0.00000 | #15 |

## 各 FOV 點的 noise floor(跨 Zernike 平均)

| FOV | mean std |
|---|---|
| #12 (row 2, col 2) | 0.08641 |
| #16 (row 2, col 6) | 0.08465 |
| #19 (row 2, col 9) | 0.08157 |
| #52 (row 6, col 2) | 0.08445 |
| #56 (row 6, col 6) | 0.08124 |
| #59 (row 6, col 9) | 0.08269 |
| #82 (row 9, col 2) | 0.07562 |
| #86 (row 9, col 6) | 0.07872 |
| #89 (row 9, col 9) | 0.08243 |

## 完整 std 矩陣 (Zernike × FOV)

| 係數 \ FOV | #12 | #16 | #19 | #52 | #56 | #59 | #82 | #86 | #89 |
|---|---|---|---|---|---|---|---|---|---|
| x1 → Z2 Y-tilt (locked=0) | 0.22945 | 0.22957 | 0.22504 | 0.25914 | 0.19231 | 0.22085 | 0.18866 | 0.22933 | 0.22632 |
| x2 → Z3 X-tilt (locked=0) | 0.25560 | 0.19985 | 0.20869 | 0.23396 | 0.23302 | 0.21309 | 0.21737 | 0.20569 | 0.20493 |
| x3 → Z4 astig 45° (sin 2φ) | 0.06175 | 0.06032 | 0.04363 | 0.03768 | 0.03429 | 0.03536 | 0.02617 | 0.01531 | 0.04175 |
| x4 → Z5 defocus | 0.37707 | 0.37494 | 0.37453 | 0.35242 | 0.38929 | 0.36563 | 0.33402 | 0.36206 | 0.39167 |
| x5 → Z6 astig 0° (cos 2φ) | 0.10142 | 0.10142 | 0.10142 | 0.10142 | 0.10142 | 0.10142 | 0.10142 | 0.10142 | 0.10142 |
| x6 → Z7 trefoil (sin 3φ) | 0.03519 | 0.04576 | 0.04081 | 0.03518 | 0.04573 | 0.04576 | 0.03518 | 0.03514 | 0.04577 |
| x7 → Z8 coma Y (sin φ) | 0.03325 | 0.02732 | 0.03111 | 0.03212 | 0.02716 | 0.02714 | 0.03253 | 0.03239 | 0.03101 |
| x8 → Z9 coma X (cos φ) | 0.00104 | 0.01267 | 0.02607 | 0.00000 | 0.02002 | 0.00000 | 0.02412 | 0.01311 | 0.00101 |
| x9 → Z10 trefoil (cos 3φ) | 0.05070 | 0.05070 | 0.00012 | 0.05071 | 0.02542 | 0.05066 | 0.00000 | 0.04788 | 0.05071 |
| x10 → Z11 quadrafoil (sin 4φ) | 0.00812 | 0.00766 | 0.00599 | 0.00733 | 0.00641 | 0.00668 | 0.00709 | 0.00890 | 0.00784 |
| x11 → Z12 sec astig (sin 2φ) | 0.00783 | 0.00728 | 0.00731 | 0.00764 | 0.00666 | 0.00831 | 0.00618 | 0.00657 | 0.00755 |
| x12 → Z13 spherical | 0.11517 | 0.13235 | 0.13903 | 0.12932 | 0.11700 | 0.14576 | 0.14232 | 0.10347 | 0.10661 |
| x13 → Z14 sec astig (cos 2φ) | 0.01014 | 0.01014 | 0.01014 | 0.01014 | 0.01014 | 0.01014 | 0.01014 | 0.01014 | 0.01014 |
| x14 → Z15 quadrafoil (cos 4φ) | 0.00946 | 0.00975 | 0.00966 | 0.00973 | 0.00976 | 0.00956 | 0.00903 | 0.00946 | 0.00969 |
| x15 → AC amplitude | 0.00000 | 0.00000 | 0.00000 | 0.00000 | 0.00000 | 0.00000 | 0.00000 | 0.00000 | 0.00000 |

## 後續行動建議

1. 把 `noise_floor.json`(本目錄旁邊)當成 Test 1 z-score 的分母 (`noise_floor_std`)。
2. 之後 L1 (重拍 100 張) 跑完後,跨 trial 算同樣 std,跟本 L0 結果相減即得「拍攝噪聲淨貢獻」。
3. 若 `std rank` 顯示高階模態 (Z11–Z15) 的 std 顯著大於低階,需重看 DESIGN §7.5.1 的「可解釋模態」清單。
4. 若 FOV 一致性差,L1 之後的層也要用 per-FOV noise floor,不能合併成單一數字。

## 用到的 trial 目錄

- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setB/outputs/trial_01`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setB/outputs/trial_02`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setB/outputs/trial_03`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setB/outputs/trial_04`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setB/outputs/trial_05`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setB/outputs/trial_06`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setB/outputs/trial_07`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setB/outputs/trial_08`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setB/outputs/trial_09`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setB/outputs/trial_10`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setB/outputs/trial_11`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setB/outputs/trial_12`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setB/outputs/trial_13`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setB/outputs/trial_14`
- `PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit_setB/outputs/trial_15`
