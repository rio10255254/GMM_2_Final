# L0 跨組對比(4 組:setA, setB, setC, setD)

> 用 setA 當 mode 對齊的 reference。
> 各組設定完全相同(同 GT、同 fitter、同搜尋範圍、同 lock_tilt、同 rng 策略),只換 fov_indices。

---

## 1. 各組基本資料

| Set | FOV indices | Trials | best_k |
|---|---|---|---|
| setA | [1, 5, 10, 41, 45, 50, 91, 95, 100] | 15 | 2 |
| setB | [12, 16, 19, 52, 56, 59, 82, 86, 89] | 15 | 2 |
| setC | [30, 33, 37, 60, 63, 67, 80, 83, 87] | 15 | 2 |
| setD | [13, 14, 17, 73, 74, 77, 93, 94, 97] | 15 | 2 |

## 2. 核心結論

### ✓ 所有 4 組都偵測到 **2 個 mode**

### 主 basin 機率(對齊後)穩不穩?

| Set | 主 basin 機率 | 次 basin 機率 | 對齊備註 |
|---|---|---|---|
| setA (ref) | 73.3% | 26.7% | (reference) |
| setB | 66.7% | 33.3% | setA mode 1 ↔ setB mode 2 |
| setC | 80.0% | 20.0% | setA mode 1 ↔ setC mode 1 |
| setD | 80.0% | 20.0% | setA mode 1 ↔ setD mode 2 |

- 主 basin 機率範圍:13.3 個百分點
- 平均 ± std:75.0% ± 6.4%(N=4)
- **機率分佈穩定** → 可以當穩定先驗

### Noise floor 量級穩不穩?

| Set | 乾淨 noise floor 中位 std |
|---|---|
| setA | 0.02863 |
| setB | 0.02732 |
| setC | 0.02247 |
| setD | 0.02302 |

- 跨組差距:**21.5%**(這條是 §6 要深挖的問題)

### Top 1 區別維度跨組一致嗎?

| Set | Top 1 區別維度 |
|---|---|
| setA | x4 → Z5 defocus |
| setB | x4 → Z5 defocus |
| setC | x4 → Z5 defocus |
| setD | x4 → Z5 defocus |

**全部 4 組的 top 1 區別維度都相同**

---

## 3. Mode 對齊細節(以 setA 為基準)

### setA ↔ setB
- setA mode 1 ↔ setB mode 2(centroid 距離 = 0.0648)
- setA mode 2 ↔ setB mode 1(centroid 距離 = 0.1964)
- 組內距離 2.4165 vs 跨組對齊距離 0.1306

### setA ↔ setC
- setA mode 1 ↔ setC mode 1(centroid 距離 = 0.1745)
- setA mode 2 ↔ setC mode 2(centroid 距離 = 0.2290)
- 組內距離 2.6655 vs 跨組對齊距離 0.2018

### setA ↔ setD
- setA mode 1 ↔ setD mode 2(centroid 距離 = 0.0634)
- setA mode 2 ↔ setD mode 1(centroid 距離 = 0.2299)
- 組內距離 2.5200 vs 跨組對齊距離 0.1467

---

## 4. Reference Basins(給 attribution Test 1 用)

從 setA 的 mode centroids 抽取。完整數值寫在同目錄 `reference_basins.json`。

- Primary basin:來自 setA mode 1,機率 73.3%
- Secondary basin:來自 setA mode 2,機率 26.7%
- Basin pair distance:0.5982

---

## 5. 綜合判決

| 屬性 | 結論 |
|---|---|
| Mode 數量 = 2 | 常態 ✓ |
| 主要區別維度 | 常態 ✓ |
| Basin 機率(跨組變動 13.3%) | 常態 ✓ |
| Noise floor 量級(差 21.5%) | 大致穩定但比預期大,§6 深挖 |

---

## 6. 為什麼 noise floor 跨組差 21.5%?

### 6.1 主解佔比 vs noise floor 的關聯

| Set | 主 basin 機率 | Noise floor |
|---|---|---|
| setA | 73.3% | 0.02863 |
| setB | 66.7% | 0.02732 |
| setC | 80.0% | 0.02247 |
| setD | 80.0% | 0.02302 |

- Pearson 相關係數:**-0.814**(N=4,要小心過度詮釋)
- 看起來主解佔比越高,noise floor 越低——可能是「主解吸引力強,trial 在主解內收斂得更精確」

### 6.2 Fval 跟迭代次數跨組對比

如果 setC/setD 的 fval 中位數明顯比 setA/setB 低,代表擬合品質本身比較好,雜訊下限低是結果不是原因。

| Set | fval median | fval mean ± std | fval range | iter median | iter mean ± std |
|---|---|---|---|---|---|
| setA | 1453.11 | 1438.24 ± 57.12 | 1335.81–1530.09 | 592 | 595 ± 47 |
| setB | 1442.83 | 1437.41 ± 48.43 | 1345.20–1516.46 | 590 | 590 ± 46 |
| setC | 1400.97 | 1402.49 ± 66.79 | 1291.62–1511.89 | 576 | 578 ± 53 |
| setD | 1433.95 | 1414.66 ± 46.47 | 1347.59–1489.83 | 584 | 587 ± 51 |

### 6.3 每個視野點貢獻的 main basin 內 std

看哪些視野把組平均 noise floor 拉高。只用 trustworthy 係數平均。

**setA** — 中位 0.0173,最大 0.0274(視野 #45)

| FOV | main basin 內 std |
|---|---|
| #1 | 0.02005 |
| #5 | 0.00916 |
| #10 | 0.01734 |
| #41 | 0.02311 |
| #45 | 0.02742 |
| #50 | 0.01445 |
| #91 | 0.01576 |
| #95 | 0.02450 |
| #100 | 0.01655 |

**setB** — 中位 0.0250,最大 0.0335(視野 #12)

| FOV | main basin 內 std |
|---|---|
| #12 | 0.03351 |
| #16 | 0.02654 |
| #19 | 0.02829 |
| #52 | 0.02450 |
| #56 | 0.02504 |
| #59 | 0.01373 |
| #82 | 0.02456 |
| #86 | 0.02628 |
| #89 | 0.01292 |

**setC** — 中位 0.0171,最大 0.0325(視野 #63)

| FOV | main basin 內 std |
|---|---|
| #30 | 0.00617 |
| #33 | 0.01513 |
| #37 | 0.01709 |
| #60 | 0.01773 |
| #63 | 0.03254 |
| #67 | 0.00648 |
| #80 | 0.00444 |
| #83 | 0.02218 |
| #87 | 0.02315 |

**setD** — 中位 0.0226,最大 0.0281(視野 #17)

| FOV | main basin 內 std |
|---|---|
| #13 | 0.01016 |
| #14 | 0.02568 |
| #17 | 0.02812 |
| #73 | 0.02257 |
| #74 | 0.01909 |
| #77 | 0.02447 |
| #93 | 0.01238 |
| #94 | 0.01024 |
| #97 | 0.02257 |

---

## 7. 兩個 basin 的物理意義

### 7.1 主/次 basin 各 Zernike 中心值(用 setA)

| 係數 | 狀態 | 主 basin 中心 | 次 basin 中心 | 主−次 |
|---|---|---|---|---|
| Z2 Y-tilt (locked) | locked | +0.0238 | -0.0299 | +0.0538 |
| Z3 X-tilt (locked) | locked | +0.0254 | +0.0415 | -0.0161 |
| Z4 astig 45° | trustworthy | -0.0402 | +0.0078 | -0.0481 |
| Z5 defocus | trustworthy | +0.1420 | +0.6960 | -0.5539 |
| Z6 astig 0° | bound_saturated | +0.0273 | -0.0167 | +0.0439 |
| Z7 trefoil (sin 3φ) | bound_saturated | -0.0050 | +0.0091 | -0.0141 |
| Z8 coma Y | trustworthy | -0.0000 | +0.0093 | -0.0093 |
| Z9 coma X | trustworthy | -0.0409 | -0.0405 | -0.0004 |
| Z10 trefoil (cos 3φ) | bound_saturated | +0.0175 | +0.0139 | +0.0036 |
| Z11 quadrafoil (sin 4φ) | trustworthy | -0.0002 | -0.0002 | +0.0000 |
| Z12 sec astig (sin 2φ) | trustworthy | -0.0003 | -0.0013 | +0.0010 |
| Z13 spherical | trustworthy | +0.2765 | +0.0691 | +0.2074 |
| Z14 sec astig (cos 2φ) | bound_saturated | -0.0027 | +0.0017 | -0.0044 |
| Z15 quadrafoil (cos 4φ) | bound_saturated | +0.0098 | -0.0050 | +0.0148 |
| AC amplitude | dead | +0.8000 | +0.8000 | +0.0000 |

### 7.2 Basin pair distance 跨組變動

| Set | Basin pair distance |
|---|---|
| setA | 1.8926 |
| setB | 2.4165 |
| setC | 2.6655 |
| setD | 2.5200 |

- 跨組 min/max:1.8926 / 2.6655,變動 40.8%
- 平均 ± std:2.3736 ± 0.3366

### 7.3 主 vs 次 basin 的 fval 哪個更低?

如果次 basin fval 反而更低,代表 BADS 有 bias 不愛跑去全局最佳解;如果主 basin fval 更低,代表 BADS 確實偏好全局最佳。

| Set | 主 basin fval 中位 (N) | 次 basin fval 中位 (N) | 主−次 |
|---|---|---|---|
| setA | 1453.11 (99) | 1453.17 (36) | -0.06 |
| setB | 1442.84 (90) | 1442.83 (45) | +0.02 |
| setC | 1400.97 (108) | 1401.43 (27) | -0.46 |
| setD | 1434.39 (108) | 1433.95 (27) | +0.44 |

---

## 8. BADS 內部隨機性

### 8.1 rng seed → basin(對齊後)跨組對比

如果相同 rng seed 跨組都落到同一 basin → MATLAB rng 控制得住;如果隨機 → BADS 內部有不受控的隨機性。

| seed | setA | setB | setC | setD |
|---|---|---|---|---|
| 1 | main | sec | main | main |
| 2 | main | main | main | main |
| 3 | sec | main | main | main |
| 4 | main | sec | main | sec |
| 5 | main | main | sec | main |
| 6 | main | main | sec | main |
| 7 | main | sec | main | main |
| 8 | main | main | main | sec |
| 9 | main | main | main | sec |
| 10 | sec | sec | sec | main |
| 11 | sec | sec | main | main |
| 12 | main | main | main | main |
| 13 | main | main | main | main |
| 14 | sec | main | main | main |
| 15 | main | main | main | main |

- 跨組完全一致(同 seed 4 組都落到同 basin):4 / 15 (26.7%)
- → BADS 內部隨機性**不受 MATLAB rng 控制**(同 seed 跨組落點隨機)

### 8.2 每個 (trial, FOV) 落到主/次 basin(per-FOV nearest-basin)

用該組主 basin 在 FOV f 的 trial 平均當參考中心,看每個 (trial, FOV) 較靠近誰。
**Mixed trial** = trial 內 9 個視野不是全主也不是全次,代表 BADS 在 trial 內不同 FOV 之間有混合行為。

**setA** — Trial 內 9 視野全部一致 = 全主 11 + 全次 2;混合 2;跟 cluster 一致 13 / 15

| FOV | 落到主 basin 的比例 |
|---|---|
| #1 | 86.7% |
| #5 | 86.7% |
| #10 | 86.7% |
| #41 | 80.0% |
| #45 | 80.0% |
| #50 | 80.0% |
| #91 | 73.3% |
| #95 | 73.3% |
| #100 | 73.3% |

**setB** — Trial 內 9 視野全部一致 = 全主 10 + 全次 5;混合 0;跟 cluster 一致 15 / 15

| FOV | 落到主 basin 的比例 |
|---|---|
| #12 | 66.7% |
| #16 | 66.7% |
| #19 | 66.7% |
| #52 | 66.7% |
| #56 | 66.7% |
| #59 | 66.7% |
| #82 | 66.7% |
| #86 | 66.7% |
| #89 | 66.7% |

**setC** — Trial 內 9 視野全部一致 = 全主 12 + 全次 3;混合 0;跟 cluster 一致 15 / 15

| FOV | 落到主 basin 的比例 |
|---|---|
| #30 | 80.0% |
| #33 | 80.0% |
| #37 | 80.0% |
| #60 | 80.0% |
| #63 | 80.0% |
| #67 | 80.0% |
| #80 | 80.0% |
| #83 | 80.0% |
| #87 | 80.0% |

**setD** — Trial 內 9 視野全部一致 = 全主 12 + 全次 3;混合 0;跟 cluster 一致 15 / 15

| FOV | 落到主 basin 的比例 |
|---|---|
| #13 | 80.0% |
| #14 | 80.0% |
| #17 | 80.0% |
| #73 | 80.0% |
| #74 | 80.0% |
| #77 | 80.0% |
| #93 | 80.0% |
| #94 | 80.0% |
| #97 | 80.0% |

---

## 9. 撞邊飽和係數的 lb/ub 分佈跨組

如果同個係數跨組的撞 lb / 撞 ub 比例一致,代表「隨機選撞哪邊」這個解釋成立;如果偏移,代表撞邊有 systematic preference。

| 係數 | setA lb%/ub% | setB lb%/ub% | setC lb%/ub% | setD lb%/ub% |
|---|---|---|---|---|
| Z6 astig 0° | 42/58 | 60/40 | 93/7 | 51/49 |
| Z7 trefoil (sin 3φ) | 46/44 | 56/39 | 93/6 | 61/35 |
| Z10 trefoil (cos 3φ) | 33/66 | 26/73 | 87/10 | 47/51 |
| Z14 sec astig (cos 2φ) | 58/42 | 40/60 | 7/93 | 49/51 |
| Z15 quadrafoil (cos 4φ) | 20/74 | 32/57 | 20/70 | 19/72 |
| AC amplitude | 100/0 | 100/0 | 100/0 | 100/0 |
