# L0 深度分析報告

- Trials:15
- FOV 點數:9(file indices = [12, 16, 19, 52, 56, 59, 82, 86, 89])
- 偵測到的 mode 數:**2** (用 hierarchical clustering 自動決定)

---

## Section 1 — 解結構:BADS 落在幾個不同的 basin?

自動偵測出 **2 個 mode**(用 ward linkage hierarchical clustering,係數 mask 排除 locked + dead)。

**Mode 機率分佈**:

| Mode | Trial 數 | 機率 | 對應 trials |
|---|---|---|---|
| 1 | 5 | 33.3% | [1, 4, 7, 10, 11] |
| 2 | 10 | 66.7% | [2, 3, 5, 6, 8, 9, 12, 13, 14, 15] |

**Hierarchical clustering 候選 k(看哪個 cut 點 gap 最大):**

| k | cut distance | gap to next | 選用? |
|---|---|---|---|
| 2 | 6.1795 | 4.6129 |  ✓ 選用 |
| 3 | 1.5666 | 0.6681 |  |
| 4 | 0.8984 | 0.3212 |  |
| 5 | 0.5772 | 0.1028 |  |
| 6 | 0.4745 | 0.0036 |  |

---

## Section 2 — 每個 mode 的內部真實噪聲(同一 basin 內 BADS 抖多少)

這才是傳統意義的「演算法 noise floor」。如果 mode 內 trial 數 < 2 則無法算 std。

| Mode | Trial 數 | 內部 std 中位數 | 內部 std 平均 | 備註 |
|---|---|---|---|---|
| 1 | 5 | 0.00894 | 0.04382 | |
| 2 | 10 | 0.02620 | 0.05435 | |

**對比參考**:乾淨版 noise floor(`analyze_L0_noise_floor.py` 算的,**忽略 mode 結構**)= 跨 15 trial 直接算 std。
Section 2 的 per-mode 才是「真實 basin 內 BADS 噪聲」,是更小的數字。

### Mode 1 內部 std (跨 9 FOV 平均)

| 係數 | 內部 std (avg over FOV) |
|---|---|
| x1 → Z2 Y-tilt (locked=0) | 0.21235 |
| x2 → Z3 X-tilt (locked=0) | 0.22735 |
| x3 → Z4 astig 45° (sin 2φ) | 0.02122 |
| x4 → Z5 defocus | 0.00255 |
| x5 → Z6 astig 0° (cos 2φ) | 0.08944 |
| x6 → Z7 trefoil (sin 3φ) | 0.02475 |
| x7 → Z8 coma Y (sin φ) | 0.01868 |
| x8 → Z9 coma X (cos φ) | 0.00992 |
| x9 → Z10 trefoil (cos 3φ) | 0.02980 |
| x10 → Z11 quadrafoil (sin 4φ) | 0.00629 |
| x11 → Z12 sec astig (sin 2φ) | 0.00527 |
| x12 → Z13 spherical | 0.00000 |
| x13 → Z14 sec astig (cos 2φ) | 0.00894 |
| x14 → Z15 quadrafoil (cos 4φ) | 0.00073 |
| x15 → AC amplitude | 0.00000 |

### Mode 2 內部 std (跨 9 FOV 平均)

| 係數 | 內部 std (avg over FOV) |
|---|---|
| x1 → Z2 Y-tilt (locked=0) | 0.23102 |
| x2 → Z3 X-tilt (locked=0) | 0.22053 |
| x3 → Z4 astig 45° (sin 2φ) | 0.02760 |
| x4 → Z5 defocus | 0.06456 |
| x5 → Z6 astig 0° (cos 2φ) | 0.10541 |
| x6 → Z7 trefoil (sin 3φ) | 0.04144 |
| x7 → Z8 coma Y (sin φ) | 0.03213 |
| x8 → Z9 coma X (cos φ) | 0.01124 |
| x9 → Z10 trefoil (cos 3φ) | 0.03826 |
| x10 → Z11 quadrafoil (sin 4φ) | 0.00765 |
| x11 → Z12 sec astig (sin 2φ) | 0.00708 |
| x12 → Z13 spherical | 0.01724 |
| x13 → Z14 sec astig (cos 2φ) | 0.01054 |
| x14 → Z15 quadrafoil (cos 4φ) | 0.00055 |
| x15 → AC amplitude | 0.00000 |

---

## Section 3 — Mode 之間的距離(BADS 不同解差多少?)

### 1-2
- **總 Euclidean 距離(在 (Z×F) 空間)**:2.4165
- **最能 discriminate 這對 mode 的 5 個係數**:

| 係數 | RMS diff (跨 FOV) |
|---|---|
| x4 → Z5 defocus | 2.24401 |
| x12 → Z13 spherical | 0.77216 |
| x2 → Z3 X-tilt (locked=0) | 0.24316 |
| x1 → Z2 Y-tilt (locked=0) | 0.22924 |
| x3 → Z4 astig 45° (sin 2φ) | 0.20344 |

---

## Section 4 — 撞邊細節(撞 lb 還是 ub?)

| 係數 | lb | ub | 撞 lb % | 撞 ub % | 內部 % | 內部 std |
|---|---|---|---|---|---|---|
| x1 → Z2 Y-tilt (locked=0) | -0.300 | +0.300 | 8% | 12% | 80% | 0.19469 |
| x2 → Z3 X-tilt (locked=0) | -0.300 | +0.300 | 12% | 10% | 79% | 0.19263 |
| x3 → Z4 astig 45° (sin 2φ) | -0.100 | +0.100 | 0% | 0% | 100% | 0.04138 |
| x4 → Z5 defocus | +0.000 | +1.000 | 23% | 0% | 77% | 0.35123 |
| x5 → Z6 astig 0° (cos 2φ) | -0.100 | +0.100 | 60% | 40% | 0% | — |
| x6 → Z7 trefoil (sin 3φ) | -0.050 | +0.050 | 56% | 39% | 4% | 0.03202 |
| x7 → Z8 coma Y (sin φ) | -0.050 | +0.050 | 0% | 0% | 100% | 0.03288 |
| x8 → Z9 coma X (cos φ) | -0.050 | +0.050 | 30% | 0% | 70% | 0.01943 |
| x9 → Z10 trefoil (cos 3φ) | -0.050 | +0.050 | 26% | 73% | 1% | 0.03907 |
| x10 → Z11 quadrafoil (sin 4φ) | -0.010 | +0.010 | 15% | 9% | 76% | 0.00640 |
| x11 → Z12 sec astig (sin 2φ) | -0.010 | +0.010 | 19% | 9% | 73% | 0.00601 |
| x12 → Z13 spherical | +0.000 | +0.300 | 33% | 15% | 52% | 0.03086 |
| x13 → Z14 sec astig (cos 2φ) | -0.010 | +0.010 | 40% | 60% | 0% | — |
| x14 → Z15 quadrafoil (cos 4φ) | -0.010 | +0.010 | 32% | 57% | 11% | 0.00488 |
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
| rng(2) | 2 |
| rng(3) | 2 |
| rng(4) | 1 |
| rng(5) | 2 |
| rng(6) | 2 |
| rng(7) | 1 |
| rng(8) | 2 |
| rng(9) | 2 |
| rng(10) | 1 |
| rng(11) | 1 |
| rng(12) | 2 |
| rng(13) | 2 |
| rng(14) | 2 |
| rng(15) | 2 |

---

## Section 7 — Per-FOV 行為差異

### 7.1 各 FOV 點在不同 mode 內的內部 std 平均

| FOV | Mode 1 | Mode 2 |
|---|---|---|
| #12 | 0.04986 | 0.06227 |
| #16 | 0.04488 | 0.05510 |
| #19 | 0.04632 | 0.05277 |
| #52 | 0.05519 | 0.05579 |
| #56 | 0.03828 | 0.05512 |
| #59 | 0.04376 | 0.05002 |
| #82 | 0.04195 | 0.04755 |
| #86 | 0.03809 | 0.05718 |
| #89 | 0.03604 | 0.05336 |

### 7.2 各 FOV 點上,mode 中心之間分離度
(數字大代表這個 FOV 是 mode discriminator)

| FOV | Mode centroid separation |
|---|---|
| #12 | 0.4001 |
| #16 | 0.4166 |
| #19 | 0.4087 |
| #52 | 0.3856 |
| #56 | 0.4160 |
| #59 | 0.4072 |
| #82 | 0.3807 |
| #86 | 0.3882 |
| #89 | 0.4196 |

---

## 全局結論

- BADS 在這個 PSF 擬合問題上會落在 **2 個不同 basin**。
- **Mode 內部平均 std**:0.04909(這才是真實「演算法收斂噪聲」)
- **Mode 之間平均分離**:2.4165
- **分離 / 內部 std 比例**:49x
  → mode 之間分離不夠大,可能需要更精細的 cluster 或重新檢視 mode 偵測閾值

## 後續建議

根據本深度分析,後續設計選擇:

1. **Attribution 改成兩層**:先判 mode、再算 mode-internal z-score(如全局結論建議)
2. **Mode 機率納入治理**:如果 mode 出現機率不對稱(例如 mode 1 = 53%, mode 2 = 40%, mode 3 = 27%),代表 BADS 對不同 basin 有偏好,L1 之後要重新驗證這個機率分佈穩不穩定(同機台重拍時 mode 機率會變嗎?)
3. **撞邊係數的處理**:全部標記為 untrustworthy,不參與 noise floor 計算 → 已在 `analyze_L0_noise_floor.py` 實作
4. **死維度**:跳過 attribution 計算,因為 std=0 會讓 z-score 爆炸
