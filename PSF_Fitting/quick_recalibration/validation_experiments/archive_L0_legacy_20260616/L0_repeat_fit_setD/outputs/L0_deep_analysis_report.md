# L0 深度分析報告

- Trials:15
- FOV 點數:9(file indices = [13, 14, 17, 73, 74, 77, 93, 94, 97])
- 偵測到的 mode 數:**2** (用 hierarchical clustering 自動決定)

---

## Section 1 — 解結構:BADS 落在幾個不同的 basin?

自動偵測出 **2 個 mode**(用 ward linkage hierarchical clustering,係數 mask 排除 locked + dead)。

**Mode 機率分佈**:

| Mode | Trial 數 | 機率 | 對應 trials |
|---|---|---|---|
| 1 | 3 | 20.0% | [4, 8, 9] |
| 2 | 12 | 80.0% | [1, 2, 3, 5, 6, 7, 10, 11, 12, 13, 14, 15] |

**Hierarchical clustering 候選 k(看哪個 cut 點 gap 最大):**

| k | cut distance | gap to next | 選用? |
|---|---|---|---|
| 2 | 5.4022 | 3.6242 |  ✓ 選用 |
| 3 | 1.7780 | 0.9271 |  |
| 4 | 0.8509 | 0.2400 |  |
| 5 | 0.6110 | 0.1541 |  |
| 6 | 0.4569 | 0.1418 |  |

---

## Section 2 — 每個 mode 的內部真實噪聲(同一 basin 內 BADS 抖多少)

這才是傳統意義的「演算法 noise floor」。如果 mode 內 trial 數 < 2 則無法算 std。

| Mode | Trial 數 | 內部 std 中位數 | 內部 std 平均 | 備註 |
|---|---|---|---|---|
| 1 | 3 | 0.01155 | 0.04281 | |
| 2 | 12 | 0.01958 | 0.05049 | |

**對比參考**:乾淨版 noise floor(`analyze_L0_noise_floor.py` 算的,**忽略 mode 結構**)= 跨 15 trial 直接算 std。
Section 2 的 per-mode 才是「真實 basin 內 BADS 噪聲」,是更小的數字。

### Mode 1 內部 std (跨 9 FOV 平均)

| 係數 | 內部 std (avg over FOV) |
|---|---|
| x1 → Z2 Y-tilt (locked=0) | 0.16587 |
| x2 → Z3 X-tilt (locked=0) | 0.18849 |
| x3 → Z4 astig 45° (sin 2φ) | 0.02337 |
| x4 → Z5 defocus | 0.00434 |
| x5 → Z6 astig 0° (cos 2φ) | 0.11547 |
| x6 → Z7 trefoil (sin 3φ) | 0.04151 |
| x7 → Z8 coma Y (sin φ) | 0.02470 |
| x8 → Z9 coma X (cos φ) | 0.00400 |
| x9 → Z10 trefoil (cos 3φ) | 0.05132 |
| x10 → Z11 quadrafoil (sin 4φ) | 0.00553 |
| x11 → Z12 sec astig (sin 2φ) | 0.00595 |
| x12 → Z13 spherical | 0.00000 |
| x13 → Z14 sec astig (cos 2φ) | 0.01155 |
| x14 → Z15 quadrafoil (cos 4φ) | 0.00009 |
| x15 → AC amplitude | 0.00000 |

### Mode 2 內部 std (跨 9 FOV 平均)

| 係數 | 內部 std (avg over FOV) |
|---|---|
| x1 → Z2 Y-tilt (locked=0) | 0.21567 |
| x2 → Z3 X-tilt (locked=0) | 0.20232 |
| x3 → Z4 astig 45° (sin 2φ) | 0.03064 |
| x4 → Z5 defocus | 0.04446 |
| x5 → Z6 astig 0° (cos 2φ) | 0.10396 |
| x6 → Z7 trefoil (sin 3φ) | 0.03628 |
| x7 → Z8 coma Y (sin φ) | 0.02243 |
| x8 → Z9 coma X (cos φ) | 0.01058 |
| x9 → Z10 trefoil (cos 3φ) | 0.05213 |
| x10 → Z11 quadrafoil (sin 4φ) | 0.00800 |
| x11 → Z12 sec astig (sin 2φ) | 0.00783 |
| x12 → Z13 spherical | 0.01239 |
| x13 → Z14 sec astig (cos 2φ) | 0.01040 |
| x14 → Z15 quadrafoil (cos 4φ) | 0.00021 |
| x15 → AC amplitude | 0.00000 |

---

## Section 3 — Mode 之間的距離(BADS 不同解差多少?)

### 1-2
- **總 Euclidean 距離(在 (Z×F) 空間)**:2.5200
- **最能 discriminate 這對 mode 的 5 個係數**:

| 係數 | RMS diff (跨 FOV) |
|---|---|
| x4 → Z5 defocus | 2.30745 |
| x12 → Z13 spherical | 0.80445 |
| x1 → Z2 Y-tilt (locked=0) | 0.44674 |
| x3 → Z4 astig 45° (sin 2φ) | 0.28857 |
| x2 → Z3 X-tilt (locked=0) | 0.26635 |

---

## Section 4 — 撞邊細節(撞 lb 還是 ub?)

| 係數 | lb | ub | 撞 lb % | 撞 ub % | 內部 % | 內部 std |
|---|---|---|---|---|---|---|
| x1 → Z2 Y-tilt (locked=0) | -0.300 | +0.300 | 8% | 10% | 81% | 0.18875 |
| x2 → Z3 X-tilt (locked=0) | -0.300 | +0.300 | 8% | 11% | 81% | 0.17649 |
| x3 → Z4 astig 45° (sin 2φ) | -0.100 | +0.100 | 4% | 0% | 96% | 0.04788 |
| x4 → Z5 defocus | +0.000 | +1.000 | 24% | 2% | 73% | 0.30835 |
| x5 → Z6 astig 0° (cos 2φ) | -0.100 | +0.100 | 51% | 49% | 0% | — |
| x6 → Z7 trefoil (sin 3φ) | -0.050 | +0.050 | 61% | 35% | 4% | 0.02927 |
| x7 → Z8 coma Y (sin φ) | -0.050 | +0.050 | 0% | 0% | 100% | 0.03138 |
| x8 → Z9 coma X (cos φ) | -0.050 | +0.050 | 53% | 0% | 47% | 0.01989 |
| x9 → Z10 trefoil (cos 3φ) | -0.050 | +0.050 | 47% | 51% | 1% | 0.06555 |
| x10 → Z11 quadrafoil (sin 4φ) | -0.010 | +0.010 | 10% | 13% | 78% | 0.00669 |
| x11 → Z12 sec astig (sin 2φ) | -0.010 | +0.010 | 10% | 24% | 66% | 0.00639 |
| x12 → Z13 spherical | +0.000 | +0.300 | 20% | 32% | 48% | 0.03163 |
| x13 → Z14 sec astig (cos 2φ) | -0.010 | +0.010 | 49% | 51% | 0% | — |
| x14 → Z15 quadrafoil (cos 4φ) | -0.010 | +0.010 | 19% | 72% | 9% | 0.00519 |
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
| rng(1) | 2 |
| rng(2) | 2 |
| rng(3) | 2 |
| rng(4) | 1 |
| rng(5) | 2 |
| rng(6) | 2 |
| rng(7) | 2 |
| rng(8) | 1 |
| rng(9) | 1 |
| rng(10) | 2 |
| rng(11) | 2 |
| rng(12) | 2 |
| rng(13) | 2 |
| rng(14) | 2 |
| rng(15) | 2 |

---

## Section 7 — Per-FOV 行為差異

### 7.1 各 FOV 點在不同 mode 內的內部 std 平均

| FOV | Mode 1 | Mode 2 |
|---|---|---|
| #13 | 0.05021 | 0.04639 |
| #14 | 0.04472 | 0.05229 |
| #17 | 0.04023 | 0.05233 |
| #73 | 0.02707 | 0.05988 |
| #74 | 0.04467 | 0.05271 |
| #77 | 0.04144 | 0.04584 |
| #93 | 0.03956 | 0.04290 |
| #94 | 0.04344 | 0.04869 |
| #97 | 0.05397 | 0.05333 |

### 7.2 各 FOV 點上,mode 中心之間分離度
(數字大代表這個 FOV 是 mode discriminator)

| FOV | Mode centroid separation |
|---|---|
| #13 | 0.4095 |
| #14 | 0.3902 |
| #17 | 0.3908 |
| #73 | 0.4132 |
| #74 | 0.4257 |
| #77 | 0.4264 |
| #93 | 0.4772 |
| #94 | 0.4137 |
| #97 | 0.4270 |

---

## 全局結論

- BADS 在這個 PSF 擬合問題上會落在 **2 個不同 basin**。
- **Mode 內部平均 std**:0.04665(這才是真實「演算法收斂噪聲」)
- **Mode 之間平均分離**:2.5200
- **分離 / 內部 std 比例**:54x
  → mode 之間分離不夠大,可能需要更精細的 cluster 或重新檢視 mode 偵測閾值

## 後續建議

根據本深度分析,後續設計選擇:

1. **Attribution 改成兩層**:先判 mode、再算 mode-internal z-score(如全局結論建議)
2. **Mode 機率納入治理**:如果 mode 出現機率不對稱(例如 mode 1 = 53%, mode 2 = 40%, mode 3 = 27%),代表 BADS 對不同 basin 有偏好,L1 之後要重新驗證這個機率分佈穩不穩定(同機台重拍時 mode 機率會變嗎?)
3. **撞邊係數的處理**:全部標記為 untrustworthy,不參與 noise floor 計算 → 已在 `analyze_L0_noise_floor.py` 實作
4. **死維度**:跳過 attribution 計算,因為 std=0 會讓 z-score 爆炸
