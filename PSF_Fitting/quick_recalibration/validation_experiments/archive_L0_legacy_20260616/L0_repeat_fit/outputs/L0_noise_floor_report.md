# L0 Noise Floor 分析報告

- 生成時間:2026-05-06 19:19:41
- Trials:15
- FOV 點數:9(file indices = [1, 5, 10, 41, 45, 50, 91, 95, 100])
- Zernike + AC 維度:15
- Git commit:0c613acb6817
- Git branch:sandbox/r44
- MATLAB:25.2.0.3150157 (R2025b) Update 4

## 主結論

- **FOV 一致性良好**(max/min = 1.20,< 2)。後續 Test 1 可以用 **單一 global noise floor**,不需 per-FOV 校準。
- **全係數噪聲偏大**(中位 std = 0.04081,> 0.02);但要記住這個數字含 lock/bound/dead artifact,看下方乾淨版本。
- **乾淨 noise floor**(只算 7 個可信係數):中位 std = 0.02863
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
| x1 → Z2 Y-tilt (locked=0) | ✗ locked | 15% | 0.20019 | lock_tilt=true 強制 Z(2)/Z(3)=0,對 loss 無影響;BADS 隨便擲值 |
| x2 → Z3 X-tilt (locked=0) | ✗ locked | 19% | 0.22108 | lock_tilt=true 強制 Z(2)/Z(3)=0,對 loss 無影響;BADS 隨便擲值 |
| x3 → Z4 astig 45° (sin 2φ) | ✓ trustworthy | 2% | 0.04058 | std=±0.04177,在 search bounds 內部(撞邊 2%) |
| x4 → Z5 defocus | ✓ trustworthy | 16% | 0.30404 | std=±0.31048,在 search bounds 內部(撞邊 16%) |
| x5 → Z6 astig 0° (cos 2φ) | ✗ bound_saturated | 100% | 0.10204 | 100% 的值撞 search bounds [-0.100, +0.100];噪聲是「隨機選撞哪邊」,非真實演算法噪聲 |
| x6 → Z7 trefoil (sin 3φ) | ✗ bound_saturated | 90% | 0.04104 | 90% 的值撞 search bounds [-0.050, +0.050];噪聲是「隨機選撞哪邊」,非真實演算法噪聲 |
| x7 → Z8 coma Y (sin φ) | ✓ trustworthy | 10% | 0.02918 | std=±0.03577,在 search bounds 內部(撞邊 10%) |
| x8 → Z9 coma X (cos φ) | ✓ trustworthy | 30% | 0.00862 | std=±0.01410,在 search bounds 內部(撞邊 30%) |
| x9 → Z10 trefoil (cos 3φ) | ✗ bound_saturated | 99% | 0.04426 | 99% 的值撞 search bounds [-0.050, +0.050];噪聲是「隨機選撞哪邊」,非真實演算法噪聲 |
| x10 → Z11 quadrafoil (sin 4φ) | ✓ trustworthy | 20% | 0.00725 | std=±0.00719,在 search bounds 內部(撞邊 20%) |
| x11 → Z12 sec astig (sin 2φ) | ✓ trustworthy | 30% | 0.00792 | std=±0.00773,在 search bounds 內部(撞邊 30%) |
| x12 → Z13 spherical | ✓ trustworthy | 63% | 0.11400 | std=±0.11574,在 search bounds 內部(撞邊 63%) |
| x13 → Z14 sec astig (cos 2φ) | ✗ bound_saturated | 100% | 0.01020 | 100% 的值撞 search bounds [-0.010, +0.010];噪聲是「隨機選撞哪邊」,非真實演算法噪聲 |
| x14 → Z15 quadrafoil (cos 4φ) | ✗ bound_saturated | 94% | 0.00811 | 94% 的值撞 search bounds [-0.010, +0.010];噪聲是「隨機選撞哪邊」,非真實演算法噪聲 |
| x15 → AC amplitude | ✗ dead | 100% | 0.00000 | 跨全部 trial × FOV 完全相同(std≈0);BADS 對此維度收斂得很死,沒有可量噪聲 |

## 各 Zernike 係數的 noise floor(跨 FOV 平均)

| 係數 | mean std | mean MAD | std rank |
|---|---|---|---|
| x1 → Z2 Y-tilt (locked=0) | 0.20019 | 0.12640 | #3 |
| x2 → Z3 X-tilt (locked=0) | 0.22108 | 0.17907 | #2 |
| x3 → Z4 astig 45° (sin 2φ) | 0.04058 | 0.02934 | #8 |
| x4 → Z5 defocus | 0.30404 | 0.01163 | #1 |
| x5 → Z6 astig 0° (cos 2φ) | 0.10204 | 0.00000 | #5 |
| x6 → Z7 trefoil (sin 3φ) | 0.04104 | 0.00209 | #7 |
| x7 → Z8 coma Y (sin φ) | 0.02918 | 0.00013 | #9 |
| x8 → Z9 coma X (cos φ) | 0.00862 | 0.00002 | #11 |
| x9 → Z10 trefoil (cos 3φ) | 0.04426 | 0.00000 | #6 |
| x10 → Z11 quadrafoil (sin 4φ) | 0.00725 | 0.00600 | #14 |
| x11 → Z12 sec astig (sin 2φ) | 0.00792 | 0.00715 | #13 |
| x12 → Z13 spherical | 0.11400 | 0.00409 | #4 |
| x13 → Z14 sec astig (cos 2φ) | 0.01020 | 0.00000 | #10 |
| x14 → Z15 quadrafoil (cos 4φ) | 0.00811 | 0.00000 | #12 |
| x15 → AC amplitude | 0.00000 | 0.00000 | #15 |

## 各 FOV 點的 noise floor(跨 Zernike 平均)

| FOV | mean std |
|---|---|
| #1 (row 1, col 1) | 0.07130 |
| #5 (row 1, col 5) | 0.07483 |
| #10 (row 1, col 10) | 0.06835 |
| #41 (row 5, col 1) | 0.07559 |
| #45 (row 5, col 5) | 0.07780 |
| #50 (row 5, col 10) | 0.07692 |
| #91 (row 10, col 1) | 0.07957 |
| #95 (row 10, col 5) | 0.08200 |
| #100 (row 10, col 10) | 0.07673 |

## 完整 std 矩陣 (Zernike × FOV)

| 係數 \ FOV | #1 | #5 | #10 | #41 | #45 | #50 | #91 | #95 | #100 |
|---|---|---|---|---|---|---|---|---|---|
| x1 → Z2 Y-tilt (locked=0) | 0.17954 | 0.20690 | 0.22673 | 0.21271 | 0.23561 | 0.16249 | 0.20074 | 0.20796 | 0.16901 |
| x2 → Z3 X-tilt (locked=0) | 0.21629 | 0.18476 | 0.17706 | 0.23100 | 0.25228 | 0.23979 | 0.22120 | 0.25082 | 0.21651 |
| x3 → Z4 astig 45° (sin 2φ) | 0.05223 | 0.03865 | 0.04357 | 0.04185 | 0.03301 | 0.03287 | 0.03757 | 0.04651 | 0.03892 |
| x4 → Z5 defocus | 0.28154 | 0.33137 | 0.25355 | 0.27908 | 0.30293 | 0.32807 | 0.32263 | 0.32132 | 0.31583 |
| x5 → Z6 astig 0° (cos 2φ) | 0.10328 | 0.10328 | 0.10328 | 0.10142 | 0.10142 | 0.10142 | 0.10142 | 0.10142 | 0.10142 |
| x6 → Z7 trefoil (sin 3φ) | 0.04474 | 0.04577 | 0.02960 | 0.04140 | 0.04598 | 0.03518 | 0.04577 | 0.03519 | 0.04577 |
| x7 → Z8 coma Y (sin φ) | 0.02441 | 0.02277 | 0.02953 | 0.02668 | 0.02603 | 0.03540 | 0.03145 | 0.03771 | 0.02863 |
| x8 → Z9 coma X (cos φ) | 0.00103 | 0.00000 | 0.02454 | 0.00000 | 0.00096 | 0.01174 | 0.01205 | 0.01279 | 0.01447 |
| x9 → Z10 trefoil (cos 3φ) | 0.04878 | 0.05164 | 0.00017 | 0.04879 | 0.04812 | 0.04879 | 0.05071 | 0.05070 | 0.05066 |
| x10 → Z11 quadrafoil (sin 4φ) | 0.00845 | 0.00686 | 0.00687 | 0.00636 | 0.00866 | 0.00694 | 0.00661 | 0.00694 | 0.00759 |
| x11 → Z12 sec astig (sin 2φ) | 0.00909 | 0.00760 | 0.00838 | 0.00779 | 0.00772 | 0.00859 | 0.00769 | 0.00735 | 0.00705 |
| x12 → Z13 spherical | 0.08282 | 0.10556 | 0.10466 | 0.11843 | 0.08606 | 0.12421 | 0.13647 | 0.13195 | 0.13584 |
| x13 → Z14 sec astig (cos 2φ) | 0.01033 | 0.01033 | 0.01033 | 0.01014 | 0.01014 | 0.01014 | 0.01014 | 0.01014 | 0.01014 |
| x14 → Z15 quadrafoil (cos 4φ) | 0.00700 | 0.00704 | 0.00703 | 0.00821 | 0.00805 | 0.00823 | 0.00915 | 0.00915 | 0.00915 |
| x15 → AC amplitude | 0.00000 | 0.00000 | 0.00000 | 0.00000 | 0.00000 | 0.00000 | 0.00000 | 0.00000 | 0.00000 |

## 後續行動建議

1. 把 `noise_floor.json`(本目錄旁邊)當成 Test 1 z-score 的分母 (`noise_floor_std`)。
2. 之後 L1 (重拍 100 張) 跑完後,跨 trial 算同樣 std,跟本 L0 結果相減即得「拍攝噪聲淨貢獻」。
3. 若 `std rank` 顯示高階模態 (Z11–Z15) 的 std 顯著大於低階,需重看 DESIGN §7.5.1 的「可解釋模態」清單。
4. 若 FOV 一致性差,L1 之後的層也要用 per-FOV noise floor,不能合併成單一數字。

## 用到的 trial 目錄

- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit\outputs\trial_01`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit\outputs\trial_02`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit\outputs\trial_03`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit\outputs\trial_04`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit\outputs\trial_05`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit\outputs\trial_06`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit\outputs\trial_07`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit\outputs\trial_08`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit\outputs\trial_09`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit\outputs\trial_10`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit\outputs\trial_11`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit\outputs\trial_12`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit\outputs\trial_13`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit\outputs\trial_14`
- `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_repeat_fit\outputs\trial_15`
