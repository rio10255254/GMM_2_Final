# L0 深度分析報告

- Trials:15
- FOV 點數:9(file indices = [1, 5, 10, 41, 45, 50, 91, 95, 100])
- 偵測到的 mode 數:**2** (用 hierarchical clustering 自動決定)

---

## Section 1 — 解結構:BADS 落在幾個不同的 basin?

自動偵測出 **2 個 mode**(用 ward linkage hierarchical clustering,係數 mask 排除 locked + dead)。

**Mode 機率分佈**:

| Mode | Trial 數 | 機率 | 對應 trials |
|---|---|---|---|
| 1 | 11 | 73.3% | [1, 2, 4, 5, 6, 7, 8, 9, 12, 13, 15] |
| 2 | 4 | 26.7% | [3, 10, 11, 14] |

**Hierarchical clustering 候選 k(看哪個 cut 點 gap 最大):**

| k | cut distance | gap to next | 選用? |
|---|---|---|---|
| 2 | 4.4468 | 2.0112 |  ✓ 選用 |
| 3 | 2.4355 | 0.8380 |  |
| 4 | 1.5976 | 0.1621 |  |
| 5 | 1.4355 | 0.8374 |  |
| 6 | 0.5981 | 0.1913 |  |

---

## Section 2 — 每個 mode 的內部真實噪聲(同一 basin 內 BADS 抖多少)

這才是傳統意義的「演算法 noise floor」。如果 mode 內 trial 數 < 2 則無法算 std。

| Mode | Trial 數 | 內部 std 中位數 | 內部 std 平均 | 備註 |
|---|---|---|---|---|
| 1 | 11 | 0.02329 | 0.05054 | |
| 2 | 4 | 0.01676 | 0.07046 | |

**對比參考**:乾淨版 noise floor(`analyze_L0_noise_floor.py` 算的,**忽略 mode 結構**)= 跨 15 trial 直接算 std。
Section 2 的 per-mode 才是「真實 basin 內 BADS 噪聲」,是更小的數字。

### Mode 1 內部 std (跨 9 FOV 平均)

| 係數 | 內部 std (avg over FOV) |
|---|---|
| x1 → Z2 Y-tilt (locked=0) | 0.20693 |
| x2 → Z3 X-tilt (locked=0) | 0.22267 |
| x3 → Z4 astig 45° (sin 2φ) | 0.03049 |
| x4 → Z5 defocus | 0.03658 |
| x5 → Z6 astig 0° (cos 2φ) | 0.10090 |
| x6 → Z7 trefoil (sin 3φ) | 0.04141 |
| x7 → Z8 coma Y (sin φ) | 0.03079 |
| x8 → Z9 coma X (cos φ) | 0.00869 |
| x9 → Z10 trefoil (cos 3φ) | 0.04474 |
| x10 → Z11 quadrafoil (sin 4φ) | 0.00695 |
| x11 → Z12 sec astig (sin 2φ) | 0.00781 |
| x12 → Z13 spherical | 0.00961 |
| x13 → Z14 sec astig (cos 2φ) | 0.01009 |
| x14 → Z15 quadrafoil (cos 4φ) | 0.00047 |
| x15 → AC amplitude | 0.00000 |

### Mode 2 內部 std (跨 9 FOV 平均)

| 係數 | 內部 std (avg over FOV) |
|---|---|
| x1 → Z2 Y-tilt (locked=0) | 0.16282 |
| x2 → Z3 X-tilt (locked=0) | 0.22611 |
| x3 → Z4 astig 45° (sin 2φ) | 0.03959 |
| x4 → Z5 defocus | 0.27303 |
| x5 → Z6 astig 0° (cos 2φ) | 0.11031 |
| x6 → Z7 trefoil (sin 3φ) | 0.03452 |
| x7 → Z8 coma Y (sin φ) | 0.02175 |
| x8 → Z9 coma X (cos φ) | 0.00944 |
| x9 → Z10 trefoil (cos 3φ) | 0.04702 |
| x10 → Z11 quadrafoil (sin 4φ) | 0.00781 |
| x11 → Z12 sec astig (sin 2φ) | 0.00764 |
| x12 → Z13 spherical | 0.09869 |
| x13 → Z14 sec astig (cos 2φ) | 0.01103 |
| x14 → Z15 quadrafoil (cos 4φ) | 0.00718 |
| x15 → AC amplitude | 0.00000 |

---

## Section 3 — Mode 之間的距離(BADS 不同解差多少?)

### 1-2
- **總 Euclidean 距離(在 (Z×F) 空間)**:1.8926
- **最能 discriminate 這對 mode 的 5 個係數**:

| 係數 | RMS diff (跨 FOV) |
|---|---|
| x4 → Z5 defocus | 1.69752 |
| x12 → Z13 spherical | 0.65650 |
| x1 → Z2 Y-tilt (locked=0) | 0.36473 |
| x2 → Z3 X-tilt (locked=0) | 0.27958 |
| x3 → Z4 astig 45° (sin 2φ) | 0.15578 |

---

## Section 4 — 撞邊細節(撞 lb 還是 ub?)

| 係數 | lb | ub | 撞 lb % | 撞 ub % | 內部 % | 內部 std |
|---|---|---|---|---|---|---|
| x1 → Z2 Y-tilt (locked=0) | -0.300 | +0.300 | 8% | 7% | 85% | 0.18666 |
| x2 → Z3 X-tilt (locked=0) | -0.300 | +0.300 | 8% | 11% | 81% | 0.19820 |
| x3 → Z4 astig 45° (sin 2φ) | -0.100 | +0.100 | 2% | 0% | 98% | 0.04076 |
| x4 → Z5 defocus | +0.000 | +1.000 | 15% | 1% | 84% | 0.29970 |
| x5 → Z6 astig 0° (cos 2φ) | -0.100 | +0.100 | 42% | 58% | 0% | — |
| x6 → Z7 trefoil (sin 3φ) | -0.050 | +0.050 | 46% | 44% | 10% | 0.03707 |
| x7 → Z8 coma Y (sin φ) | -0.050 | +0.050 | 0% | 10% | 90% | 0.03390 |
| x8 → Z9 coma X (cos φ) | -0.050 | +0.050 | 30% | 0% | 70% | 0.01523 |
| x9 → Z10 trefoil (cos 3φ) | -0.050 | +0.050 | 33% | 66% | 1% | — |
| x10 → Z11 quadrafoil (sin 4φ) | -0.010 | +0.010 | 8% | 12% | 80% | 0.00627 |
| x11 → Z12 sec astig (sin 2φ) | -0.010 | +0.010 | 16% | 14% | 70% | 0.00652 |
| x12 → Z13 spherical | +0.000 | +0.300 | 20% | 43% | 37% | 0.03935 |
| x13 → Z14 sec astig (cos 2φ) | -0.010 | +0.010 | 58% | 42% | 0% | — |
| x14 → Z15 quadrafoil (cos 4φ) | -0.010 | +0.010 | 20% | 74% | 6% | 0.00224 |
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
| rng(3) | 2 |
| rng(4) | 1 |
| rng(5) | 1 |
| rng(6) | 1 |
| rng(7) | 1 |
| rng(8) | 1 |
| rng(9) | 1 |
| rng(10) | 2 |
| rng(11) | 2 |
| rng(12) | 1 |
| rng(13) | 1 |
| rng(14) | 2 |
| rng(15) | 1 |

---

## Section 7 — Per-FOV 行為差異

### 7.1 各 FOV 點在不同 mode 內的內部 std 平均

| FOV | Mode 1 | Mode 2 |
|---|---|---|
| #1 | 0.05101 | 0.08331 |
| #5 | 0.04545 | 0.09217 |
| #10 | 0.04539 | 0.06671 |
| #41 | 0.05477 | 0.08045 |
| #45 | 0.05989 | 0.08470 |
| #50 | 0.04571 | 0.08502 |
| #91 | 0.04837 | 0.04815 |
| #95 | 0.05680 | 0.04768 |
| #100 | 0.04750 | 0.04598 |

### 7.2 各 FOV 點上,mode 中心之間分離度
(數字大代表這個 FOV 是 mode discriminator)

| FOV | Mode centroid separation |
|---|---|
| #1 | 0.2384 |
| #5 | 0.2563 |
| #10 | 0.2485 |
| #41 | 0.2816 |
| #45 | 0.2774 |
| #50 | 0.3267 |
| #91 | 0.3980 |
| #95 | 0.3817 |
| #100 | 0.3796 |

---

## 全局結論

- BADS 在這個 PSF 擬合問題上會落在 **2 個不同 basin**。
- **Mode 內部平均 std**:0.06050(這才是真實「演算法收斂噪聲」)
- **Mode 之間平均分離**:1.8926
- **分離 / 內部 std 比例**:31x
  → mode 之間分離不夠大,可能需要更精細的 cluster 或重新檢視 mode 偵測閾值

## 後續建議

根據本深度分析,後續設計選擇:

1. **Attribution 改成兩層**:先判 mode、再算 mode-internal z-score(如全局結論建議)
2. **Mode 機率納入治理**:如果 mode 出現機率不對稱(例如 mode 1 = 53%, mode 2 = 40%, mode 3 = 27%),代表 BADS 對不同 basin 有偏好,L1 之後要重新驗證這個機率分佈穩不穩定(同機台重拍時 mode 機率會變嗎?)
3. **撞邊係數的處理**:全部標記為 untrustworthy,不參與 noise floor 計算 → 已在 `analyze_L0_noise_floor.py` 實作
4. **死維度**:跳過 attribution 計算,因為 std=0 會讓 z-score 爆炸
