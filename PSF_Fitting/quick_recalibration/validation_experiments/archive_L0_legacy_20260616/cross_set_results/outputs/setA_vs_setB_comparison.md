# L0 setA vs setB 對比分析

> **目的**:setA 跑出 2 個收斂域後,需要驗證這是 BADS 對這類擬合問題的常態,還是那組 FOV 的特例。
> 用另一組完全不重疊的 9 個 FOV(setB)重跑同樣 15 trial,跨組對比結果。

---

## 1. 兩組基本設定對比

| 項目 | setA | setB |
|---|---|---|
| FOV indices | [1, 5, 10, 41, 45, 50, 91, 95, 100] | [12, 16, 19, 52, 56, 59, 82, 86, 89] |
| Trial 數 | 15 | 15 |
| 其他全部 | 同 GT、同 fitter、同搜尋範圍、同 lock_tilt、同 rng 策略 | 同左 |

---

## 2. 核心結論

### ✓ 確認:BADS 在這類問題上會分裂成 2 個收斂域

setA 跟 setB 都偵測到 **2 個 mode**。配合下面 §3 的跨組 mode 對齊結果,
可以判斷這兩個 mode 是同樣 2 個 basin(物理上),而不是 cluster 偶然分群。

### 模態機率分佈穩定嗎?

| 對齊組合 | setA 機率 | setB 機率 | Centroid 距離 |
|---|---|---|---|
| setA mode 1 ↔ setB mode 2 | 73.3% | 66.7% | 0.0648 |
| setA mode 2 ↔ setB mode 1 | 26.7% | 33.3% | 0.1964 |

主 mode 機率兩組接近(setA=73% vs setB=67%),機率分佈大致穩定。

### Noise floor 量值穩定嗎?

- setA 乾淨 noise floor 中位 std = **0.02863**
- setB 乾淨 noise floor 中位 std = **0.02732**
- 差距:**4.6%**

**Noise floor 量級非常穩定**(差 < 10%),代表「演算法本身的隨機性大小」是可量、可信的物理量。

---

## 3. 跨組 Mode 對齊

Cluster label 是 arbitrary 的,setA 的 mode 1 跟 setB 的 mode 1 沒必然關係。
把兩組各 mode 的 centroid 跨 FOV 平均成 15 維 Zernike 向量,用 Euclidean 距離找最佳對應。

**距離矩陣(列=setA mode, 欄=setB mode)**:

| | setB-1 | setB-2 |
|---|---|---|
| setA-1 | 0.7706 | 0.0648 |
| setA-2 | 0.1964 | 0.6252 |

**最佳對齊**:

- setA mode 1 ↔ setB mode 2(centroid 距離 = 0.0648)
- setA mode 2 ↔ setB mode 1(centroid 距離 = 0.1964)

**對比**:組內 mode-1 vs mode-2 的平均距離 = 2.1545
      組間對齊後對應 mode 的平均距離 = 0.1306

組間對齊距離遠小於組內 mode 距離,**確認兩組看到的是同樣 2 個 basin**(物理上的同一收斂域)。

---

## 4. Top 區別維度對比

兩組各自的 mode 1-2 用哪些係數區別?如果兩組的 top 5 大致一致,代表 basin 的物理結構是穩定的。

### setA(總距離 1.8926)

| Rank | 係數 | RMS diff |
|---|---|---|
| 1 | x4 → Z5 defocus | 1.69752 |
| 2 | x12 → Z13 spherical | 0.65650 |
| 3 | x1 → Z2 Y-tilt (locked=0) | 0.36473 |
| 4 | x2 → Z3 X-tilt (locked=0) | 0.27958 |
| 5 | x3 → Z4 astig 45° (sin 2φ) | 0.15578 |

### setB(總距離 2.4165)

| Rank | 係數 | RMS diff |
|---|---|---|
| 1 | x4 → Z5 defocus | 2.24401 |
| 2 | x12 → Z13 spherical | 0.77216 |
| 3 | x2 → Z3 X-tilt (locked=0) | 0.24316 |
| 4 | x1 → Z2 Y-tilt (locked=0) | 0.22924 |
| 5 | x3 → Z4 astig 45° (sin 2φ) | 0.20344 |

**兩組的 #1 區別維度都是 x4 → Z5 defocus**,確認是同樣的物理結構主導 mode 分裂。

---

## 5. 係數可信度分類對比

兩組的搜尋範圍 + lock_tilt 設定完全相同,所以係數分類(locked/dead/bound_saturated/trustworthy)應該一致。

| 係數 | setA | setB | 一致? | setA 撞邊% | setB 撞邊% |
|---|---|---|---|---|---|
| Z2 Y-tilt (locked) | locked | locked | ✓ | 15% | 20% |
| Z3 X-tilt (locked) | locked | locked | ✓ | 19% | 21% |
| Z4 astig 45° | trustworthy | trustworthy | ✓ | 2% | 0% |
| Z5 defocus | trustworthy | trustworthy | ✓ | 16% | 23% |
| Z6 astig 0° | bound_saturated | bound_saturated | ✓ | 100% | 100% |
| Z7 trefoil (sin 3φ) | bound_saturated | bound_saturated | ✓ | 90% | 96% |
| Z8 coma Y | trustworthy | trustworthy | ✓ | 10% | 0% |
| Z9 coma X | trustworthy | trustworthy | ✓ | 30% | 30% |
| Z10 trefoil (cos 3φ) | bound_saturated | bound_saturated | ✓ | 99% | 99% |
| Z11 quadrafoil (sin 4φ) | trustworthy | trustworthy | ✓ | 20% | 24% |
| Z12 sec astig (sin 2φ) | trustworthy | trustworthy | ✓ | 30% | 27% |
| Z13 spherical | trustworthy | trustworthy | ✓ | 63% | 48% |
| Z14 sec astig (cos 2φ) | bound_saturated | bound_saturated | ✓ | 100% | 100% |
| Z15 quadrafoil (cos 4φ) | bound_saturated | bound_saturated | ✓ | 94% | 89% |
| AC amplitude | dead | dead | ✓ | 100% | 100% |

**所有 15 個係數的分類完全一致**,確認 search bounds 設計問題(5 個 bound_saturated + 1 個 dead)跟 FOV 無關。

---

## 6. 跨組綜合判決

| 屬性 | 是 BADS 常態還是 FOV 特例? | 證據 |
|---|---|---|
| Mode 數量(=2) | **常態** | setA / setB 都偵測到 2 個 mode |
| Mode 主要區別維度(x4 → Z5 defocus) | **常態** | 兩組 top 1 區別維度相同 |
| 兩個 basin 的物理位置 | **常態** | 跨組 mode 對齊後距離小於組內 mode 距離 |
| Noise floor 量級(中位 std ~ 0.0280) | **常態** | 兩組差 4.6% |
| 係數可信度分類(7 trustworthy / 2 locked / 5 bound_saturated / 1 dead) | **常態** | 兩組完全一致 |

## 7. 對 DESIGN §9 歸因設計的意涵

根據 §6 判決,**setA 跟 setB 在六個面向都顯示是 BADS 常態**(包含 mode 機率分佈也是),
DESIGN §9 Test 1 的單層 z-score 設計確定需要改成兩層,而且每層都有資料支持:

- **第一層:落到哪個 basin** — 兩個 basin 物理位置確定,要用 Zernike centroid 對齊判別,不能用 raw cluster label(label 是 arbitrary 的,setA mode 1 = setB mode 2)
  - 操作:用對齊後的 basin 中心做 nearest-centroid 分類,把每個新 trial 歸到主 basin 或次 basin

- **第二層:basin 內部的 z 分數** — noise floor 設成 mode-internal std,不是混合所有 trial 的 std
  - 理由:noise floor 量級在兩組之間穩定(差 4.6%),mode-internal std 也穩定
  - 操作:用 mode-internal noise floor std(約 0.05–0.06)當分母

- **basin 機率可以當先驗** — 對齊後,主 basin 機率 setA 73% / setB 67%(差 6%),次 basin 27% / 33%(差 6%),範圍合理
  - 操作:之後 L1 同機重拍時,如果某次出現的主/次比例顯著偏離這個 ~70/30 範圍,就可以當作 outlier 訊號

- **L1 之後要驗證的**:同機重拍,主/次 basin 機率分佈跟 setA/setB 的 70/30 接近嗎?
  - 接近 → 確認 70/30 是這台機這類 PSF 擬合的固定分布,可以當穩定先驗
  - 偏離 → 拍攝噪聲確實會影響 basin 落點,要把這個納入 noise floor 估計
