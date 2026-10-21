# DESIGN §9 歸因設計改寫建議草稿

> **狀態**:草稿,等使用者(設計作者)review 採納
> **建立日期**:2026-05-14
> **依據證據**:`validation_experiments/setA_vs_setB_comparison.md`(setC/setD 跑完後會更新)
> **採納後處置**:把建議內容 copy 到 [`DESIGN_TW.md`](DESIGN_TW.md) §9,然後刪掉本檔

---

## 為什麼要改

原 DESIGN §9.3 Test 1 假設「對單一 noise floor 算 z 分數」。
L0 setA + setB(各 9 FOV × 15 trial)跑完後,證據顯示:

1. **BADS 對這類 PSF 擬合會分裂成 2 個收斂域**——不是單一收斂
2. **兩個 basin 的物理位置跨組穩定**——setA/setB 對齊後 centroid 距離 0.06 / 0.20,遠小於組內 mode 距離 2.15
3. **主/次 basin 機率主 70%、次 30% 跨組穩定**——setA(73/27)vs setB(67/33),差 6 個百分點
4. **混合所有 trial 算 std 會嚴重低估真實演算法噪聲**——乾淨混合 std ≈ 0.028,basin-internal std ≈ 0.05;混合版本被「mode 之間的距離」拉大,不是「演算法收斂噪聲」

→ Test 1 的單層 z 分數設計確定要改成兩層(先判 basin,再算 basin-internal z 分數)。

---

## 新版 §9.3(替換用)

### 9.3 Test 1 — 擬合 basin 結構測試

**問題**:差異 Δ 是不是只是 BADS 本身的收斂隨機性?

L0 證據顯示 BADS 不是單一收斂,而是落在兩個 basin 之一。所以這個 Test 拆成兩層:

#### 9.3.1 Layer 1a — Basin 判別(必要)

從 L0 累積的 setA/setB(以後 setC/setD)mode centroids,把 15 維 Zernike 跨 FOV 平均後當作 **reference basins**(每個 basin 一個 reference vector,目前 2 個)。注意:

- **raw cluster label 是 arbitrary 的**——setA 的 mode 1 = setB 的 mode 2。
  用 reference centroid 對齊,而不是用 cluster id
- reference basins 寫在 `quick_recalibration/reference_basins.json`,從 L0 跨組對比的 mode 對齊結果生成

對 fitted trial 的 15 維係數向量做 nearest-neighbor 分類:

```
distance_to_basin_k = ||fitted_coef - reference_basins[k]||  for k in {主, 次}
assigned_basin       = argmin_k(distance_to_basin_k)
d_to_assigned        = distance_to_basin_k[assigned_basin]
```

**flag 條件**:`d_to_assigned > basin_pair_distance × 0.5`(超過兩個 basin 中心一半的距離) → "between-basin",可能是 outlier 或新的 basin,**警示但不直接判決**

#### 9.3.2 Layer 1b — Basin 內 z 分數(必要)

對 `assigned_basin` 內的 basin-internal std 算 z 分數:

```
basin_center        = reference_basins[assigned_basin]
basin_internal_std  = noise_floor_basin[assigned_basin]   # 從 L0 deep_analysis 取
Δ_from_center       = |fitted_coef - basin_center|
z                   = Δ_from_center / basin_internal_std
```

**只對 trustworthy 係數算**(L0 已標記 7 個:Z4, Z5, Z7, Z8, Z11, Z12, Z13):
- locked(Z2, Z3 tilt):跳過,std 是 artifact
- bound_saturated(Z6, Z7-sin, Z10, Z14, Z15):跳過,std 是 artifact
- dead(AC amplitude):跳過,std=0 會讓 z 爆炸

**判決**:
```
if median(|z|) < 2:
    判決 = "no_real_change"
    停止後續測試
else:
    繼續 Test 2
```

#### 9.3.3 Layer 1c — Basin 機率核對(advisory,L1 後升級)

對同一台機跑多次擬合,統計主/次 basin 落點機率。

- L0 證據:setA 73/27、setB 67/33。預期範圍 70/30 ± 10
- 如果新機跑出來明顯偏離(例如 40/60、或 95/5),flag "unusual basin distribution"

**目前 advisory**——L1 跑完(同機重拍多次)再決定要不要升級成 mandatory。
理由:目前還沒驗證「同機重拍時 basin 機率會跟著拍攝噪聲變嗎」。如果會,Layer 1c 才有意義。

---

## §9.6 三測試綜合判決表(更新)

原表的第一欄(Test 1)要改:

| Test 1 (新) | Test 2 | Test 3 | 綜合判決 | 建議行動 |
|---|---|---|---|---|
| basin 內 median(\|z\|) < 2 | — | — | no_real_change | 收下校正結果 |
| basin 內 median(\|z\|) ≥ 2 | 無結構 | — | fitting_noise_artifact | 增加 BADS iterations 或加正則化 |
| basin 內 median(\|z\|) ≥ 2 | 有結構 | 集中可解釋模態 | real_machine_change_explainable | 收下,記錄變化模態 |
| basin 內 median(\|z\|) ≥ 2 | 有結構 | 部分高階 | real_change_with_high_order_warning | 收下但 flag |
| basin 內 median(\|z\|) ≥ 2 | 有結構 | 集中不可解釋 | suspicious_overfit | **不收**,降級 L2 重跑 |
| d_to_assigned > basin_pair_distance × 0.5 | — | — | between-basin | 警示,可能是新 basin 或 outlier;以 Layer 1c 機率分佈輔助判讀 |

Test 2(空間結構)跟 Test 3(模態定位)邏輯不變。

---

## §9.7 歸因報告輸出格式(微調)

原本的歸因報告增加 Test 1 的兩層細節:

```markdown
## Test 1:擬合 basin 結構測試

### Layer 1a — Basin 判別
- 距離到主 basin centroid:0.45
- 距離到次 basin centroid:1.87
- assigned_basin:主 basin
- d_to_assigned / (basin_pair_distance × 0.5):0.45 / 1.07 = 0.42 → 在 basin 範圍內,正常

### Layer 1b — Basin 內 z 分數
- 用 7 個 trustworthy 係數
- median(|z|):3.5(≥ 2,**判決:有實質差異**)
- 各係數 z-score:[圖]

### Layer 1c — Basin 機率核對(advisory)
- 該機跑 N 次,主 basin 機率 = 0.78,次 basin 機率 = 0.22
- 跟 L0 reference 70/30 接近,無警示
```

---

## 對 §10(A 階段算法驗證實驗)的連動更新

§10.2 的「L0 完成後產出什麼」要更新:

| 原本 | 改成 |
|---|---|
| `noise_floor_std`(per FOV, per Zernike) | `noise_floor_basin[basin_k]`(per basin, per trustworthy 係數);跟原本的全係數 std 並列保留(對照用) |
| (沒提) | `reference_basins.json`(2 個 basin 的 centroid 向量) |
| (沒提) | `basin_pair_distance`(兩個 basin 中心的距離,當作 flag 門檻) |

§10.6.1 校準 Test 1 noise floor 的描述,改成「校準 basin-internal noise floor」。

---

## 採納步驟(等使用者決定)

1. 把本文 §「新版 §9.3」整段 copy 到 `DESIGN_TW.md` §9.3(替換原本內容)
2. 把本文 §「§9.6 三測試綜合判決表(更新)」的表格 copy 到 `DESIGN_TW.md` §9.6
3. 把本文 §「§9.7 歸因報告輸出格式」的 Test 1 區塊 copy 到 `DESIGN_TW.md` §9.7 對應位置
4. 把本文 §「§10 連動更新」的兩個 bullet 反映到 `DESIGN_TW.md` §10.2 跟 §10.6.1
5. 在 `DESIGN_TW.md` §15.3 修訂歷史加一列:
   ```
   | v0.2 | 2026-05-XX | 根據 L0 setA/setB(及 setC/setD)結果,§9.3 Test 1 改為 basin-aware 兩層設計;§9.6/§9.7/§10 連動更新 |
   ```
6. 刪掉本檔

---

## 還沒能回答、需要 L1 才能答的

- **basin 機率 70/30 在「同機重拍」時穩不穩?** L0 setA/setB 是「同次拍攝、不同 FOV」,跨拍攝的影響還沒測
- 如果不穩 → Layer 1c 要從 advisory 升級成 mandatory,而且 reference basins 可能要按 capture 重算
- 如果穩 → 維持目前 advisory 設計即可
