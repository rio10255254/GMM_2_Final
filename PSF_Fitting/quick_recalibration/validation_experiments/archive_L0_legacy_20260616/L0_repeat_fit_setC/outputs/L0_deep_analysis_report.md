# L0 深度分析報告

- Trials:15
- FOV 點數:9(file indices = [30, 33, 37, 60, 63, 67, 80, 83, 87])
- 偵測到的 mode 數:**2** (用 hierarchical clustering 自動決定)

---

## Section 1 — 解結構:BADS 落在幾個不同的 basin?

自動偵測出 **2 個 mode**(用 ward linkage hierarchical clustering,係數 mask 排除 locked + dead)。

**Mode 機率分佈**:

| Mode | Trial 數 | 機率 | 對應 trials |
|---|---|---|---|
| 1 | 12 | 80.0% | [1, 2, 3, 4, 7, 8, 9, 11, 12, 13, 14, 15] |
| 2 | 3 | 20.0% | [5, 6, 10] |

**Hierarchical clustering 候選 k(看哪個 cut 點 gap 最大):**

| k | cut distance | gap to next | 選用? |
|---|---|---|---|
| 2 | 5.5028 | 4.6811 |  ✓ 選用 |
| 3 | 0.8217 | 0.1193 |  |
| 4 | 0.7025 | 0.1127 |  |
| 5 | 0.5897 | 0.1513 |  |
| 6 | 0.4384 | 0.1364 |  |

---

## Section 2 — 每個 mode 的內部真實噪聲(同一 basin 內 BADS 抖多少)

這才是傳統意義的「演算法 noise floor」。如果 mode 內 trial 數 < 2 則無法算 std。

| Mode | Trial 數 | 內部 std 中位數 | 內部 std 平均 | 備註 |
|---|---|---|---|---|
| 1 | 12 | 0.00018 | 0.03329 | |
| 2 | 3 | 0.00941 | 0.04150 | |

**對比參考**:乾淨版 noise floor(`analyze_L0_noise_floor.py` 算的,**忽略 mode 結構**)= 跨 15 trial 直接算 std。
Section 2 的 per-mode 才是「真實 basin 內 BADS 噪聲」,是更小的數字。

### Mode 1 內部 std (跨 9 FOV 平均)

| 係數 | 內部 std (avg over FOV) |
|---|---|
| x1 → Z2 Y-tilt (locked=0) | 0.19386 |
| x2 → Z3 X-tilt (locked=0) | 0.19179 |
| x3 → Z4 astig 45° (sin 2φ) | 0.02688 |
| x4 → Z5 defocus | 0.05746 |
| x5 → Z6 astig 0° (cos 2φ) | 0.00000 |
| x6 → Z7 trefoil (sin 3φ) | 0.00007 |
| x7 → Z8 coma Y (sin φ) | 0.00002 |
| x8 → Z9 coma X (cos φ) | 0.00009 |
| x9 → Z10 trefoil (cos 3φ) | 0.00029 |
| x10 → Z11 quadrafoil (sin 4φ) | 0.00630 |
| x11 → Z12 sec astig (sin 2φ) | 0.00671 |
| x12 → Z13 spherical | 0.01525 |
| x13 → Z14 sec astig (cos 2φ) | 0.00000 |
| x14 → Z15 quadrafoil (cos 4φ) | 0.00066 |
| x15 → AC amplitude | 0.00000 |

### Mode 2 內部 std (跨 9 FOV 平均)

| 係數 | 內部 std (avg over FOV) |
|---|---|
| x1 → Z2 Y-tilt (locked=0) | 0.12560 |
| x2 → Z3 X-tilt (locked=0) | 0.22707 |
| x3 → Z4 astig 45° (sin 2φ) | 0.02033 |
| x4 → Z5 defocus | 0.00434 |
| x5 → Z6 astig 0° (cos 2φ) | 0.11547 |
| x6 → Z7 trefoil (sin 3φ) | 0.02198 |
| x7 → Z8 coma Y (sin φ) | 0.03126 |
| x8 → Z9 coma X (cos φ) | 0.00422 |
| x9 → Z10 trefoil (cos 3φ) | 0.05057 |
| x10 → Z11 quadrafoil (sin 4φ) | 0.00550 |
| x11 → Z12 sec astig (sin 2φ) | 0.00461 |
| x12 → Z13 spherical | 0.00003 |
| x13 → Z14 sec astig (cos 2φ) | 0.01155 |
| x14 → Z15 quadrafoil (cos 4φ) | 0.00001 |
| x15 → AC amplitude | 0.00000 |

---

## Section 3 — Mode 之間的距離(BADS 不同解差多少?)

### 1-2
- **總 Euclidean 距離(在 (Z×F) 空間)**:2.6655
- **最能 discriminate 這對 mode 的 5 個係數**:

| 係數 | RMS diff (跨 FOV) |
|---|---|
| x4 → Z5 defocus | 2.34103 |
| x12 → Z13 spherical | 0.81047 |
| x1 → Z2 Y-tilt (locked=0) | 0.79018 |
| x2 → Z3 X-tilt (locked=0) | 0.41481 |
| x3 → Z4 astig 45° (sin 2φ) | 0.23877 |

---

## Section 4 — 撞邊細節(撞 lb 還是 ub?)

| 係數 | lb | ub | 撞 lb % | 撞 ub % | 內部 % | 內部 std |
|---|---|---|---|---|---|---|
| x1 → Z2 Y-tilt (locked=0) | -0.300 | +0.300 | 4% | 13% | 82% | 0.18498 |
| x2 → Z3 X-tilt (locked=0) | -0.300 | +0.300 | 5% | 13% | 82% | 0.18055 |
| x3 → Z4 astig 45° (sin 2φ) | -0.100 | +0.100 | 3% | 0% | 97% | 0.04010 |
| x4 → Z5 defocus | +0.000 | +1.000 | 19% | 5% | 76% | 0.28962 |
| x5 → Z6 astig 0° (cos 2φ) | -0.100 | +0.100 | 93% | 7% | 0% | — |
| x6 → Z7 trefoil (sin 3φ) | -0.050 | +0.050 | 93% | 6% | 1% | 0.02260 |
| x7 → Z8 coma Y (sin φ) | -0.050 | +0.050 | 0% | 1% | 99% | 0.01889 |
| x8 → Z9 coma X (cos φ) | -0.050 | +0.050 | 53% | 0% | 47% | 0.01126 |
| x9 → Z10 trefoil (cos 3φ) | -0.050 | +0.050 | 87% | 10% | 2% | 0.04865 |
| x10 → Z11 quadrafoil (sin 4φ) | -0.010 | +0.010 | 12% | 5% | 83% | 0.00597 |
| x11 → Z12 sec astig (sin 2φ) | -0.010 | +0.010 | 11% | 11% | 78% | 0.00535 |
| x12 → Z13 spherical | +0.000 | +0.300 | 20% | 39% | 41% | 0.03068 |
| x13 → Z14 sec astig (cos 2φ) | -0.010 | +0.010 | 7% | 93% | 0% | — |
| x14 → Z15 quadrafoil (cos 4φ) | -0.010 | +0.010 | 20% | 70% | 10% | 0.00302 |
| x15 → AC amplitude | +0.800 | +1.250 | 100% | 0% | 0% | — |

**讀法**:
- 撞 lb % + 撞 ub % > 80%:該係數的「噪聲」是「隨機選撞哪邊」(artifact)
- 撞 lb % > 30% 但 < 撞 ub %:解空間在 lb 那側可能更不確定
- 內部 % 高且內部 std 小:該係數真實量到了 BADS 收斂噪聲

---

## Section 5 — 死維度(完全沒抖動的常駐值)

| 係數 | 常駐值 | lb / ub | 位置 |
|---|---|---|---|
| x15 → AC amplitude | +0.80000 | +0.800 / +1.250 | lb |

---

## Section 6 — 隨機種子對 mode 的控制力

rng(N) 切換是否可預測落到哪個 mode?如果可預測,L0 的隨機性策略有效;如果隨機,代表 BADS 內部某些 RandStream 不受 MATLAB rng 控制。

| RNG seed | Mode |
|---|---|
| rng(1) | 1 |
| rng(2) | 1 |
| rng(3) | 1 |
| rng(4) | 1 |
| rng(5) | 2 |
| rng(6) | 2 |
| rng(7) | 1 |
| rng(8) | 1 |
| rng(9) | 1 |
| rng(10) | 2 |
| rng(11) | 1 |
| rng(12) | 1 |
| rng(13) | 1 |
| rng(14) | 1 |
| rng(15) | 1 |

---

## Section 7 — Per-FOV 行為差異

### 7.1 各 FOV 點在不同 mode 內的內部 std 平均

| FOV | Mode 1 | Mode 2 |
|---|---|---|
| #30 | 0.02692 | 0.02697 |
| #33 | 0.03462 | 0.03688 |
| #37 | 0.03703 | 0.04427 |
| #60 | 0.03416 | 0.04253 |
| #63 | 0.04395 | 0.02818 |
| #67 | 0.02742 | 0.05705 |
| #80 | 0.02369 | 0.04478 |
| #83 | 0.03755 | 0.05062 |
| #87 | 0.03429 | 0.04226 |

### 7.2 各 FOV 點上,mode 中心之間分離度
(數字大代表這個 FOV 是 mode discriminator)

| FOV | Mode centroid separation |
|---|---|
| #30 | 0.4823 |
| #33 | 0.4613 |
| #37 | 0.4290 |
| #60 | 0.3976 |
| #63 | 0.3943 |
| #67 | 0.4784 |
| #80 | 0.5086 |
| #83 | 0.4139 |
| #87 | 0.4177 |

---

## 全局結論

- BADS 在這個 PSF 擬合問題上會落在 **2 個不同 basin**。
- **Mode 內部平均 std**:0.03740(這才是真實「演算法收斂噪聲」)
- **Mode 之間平均分離**:2.6655
- **分離 / 內部 std 比例**:71x
  → mode 之間分離不夠大,可能需要更精細的 cluster 或重新檢視 mode 偵測閾值

## 後續建議

根據本深度分析,後續設計選擇:

1. **Attribution 改成兩層**:先判 mode、再算 mode-internal z-score(如全局結論建議)
2. **Mode 機率納入治理**:如果 mode 出現機率不對稱(例如 mode 1 = 53%, mode 2 = 40%, mode 3 = 27%),代表 BADS 對不同 basin 有偏好,L1 之後要重新驗證這個機率分佈穩不穩定(同機台重拍時 mode 機率會變嗎?)
3. **撞邊係數的處理**:全部標記為 untrustworthy,不參與 noise floor 計算 → 已在 `analyze_L0_noise_floor.py` 實作
4. **死維度**:跳過 attribution 計算,因為 std=0 會讓 z-score 爆炸
