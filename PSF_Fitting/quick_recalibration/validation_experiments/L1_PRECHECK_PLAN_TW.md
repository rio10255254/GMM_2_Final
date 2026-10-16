# L1 前置驗證計畫(L1 PRECHECK)

> **狀態**:計畫,等使用者進實驗室執行
> **目的**:只回答**一個關鍵問題**——主/次 basin 機率(70/30)在同機重拍時穩不穩?
> **跟完整 L1 的差異**:完整 L1 是同機重拍 100 張 × 3 次,各跑 1.5–2 hr WholeFOV。本前置版是 L0 風格的小規模(9 FOV × 15 trial),只看 basin 機率,不算完整 noise floor。

---

## 為什麼要前置驗證

L0 setA + setB(以後加 setC + setD)告訴我們:
- BADS 對這類擬合會分裂 2 個 basin(常態)
- 機率 70/30 跨 FOV 組穩定(差 6%)

**還沒回答**:**跨拍攝**呢?也就是同機台不動,只「重新拍一次照片」,主/次 basin 機率還會接近 70/30 嗎?

這個答案直接決定 [DESIGN_SECTION9_REVISION_PROPOSAL_TW.md](../DESIGN_SECTION9_REVISION_PROPOSAL_TW.md) 裡 Layer 1c(basin 機率核對)該是 advisory 還是 mandatory:

- 跨拍攝穩定(機率落在 70/30 ± 10%) → Layer 1c 維持 advisory,設計不變
- 跨拍攝不穩定(機率明顯偏離,例如 50/50 或 95/5) → Layer 1c 要 mandatory,而且 reference basins 要按 capture 重新校準

---

## 實驗設計

### 拍攝計畫

| 項目 | 設定 |
|---|---|
| 同機台 | 不動、不拆裝、不重對焦、不清鏡頭 |
| GT 樣本 | 不移動 |
| 重拍次數 | 3 次(min 2 次,3 次更穩) |
| 每次拍 | 跟現行流程一樣的全 FOV 100 張 |
| 拍攝間隔 | 短(同一個小時內結束,避免室溫漂移 > 1°C) |
| 操作者 | 同一人 |
| 環境 | 跟既有 setA/setB 拍攝時的條件對齊(室溫紀錄起來) |

**輸出**:三組「同機重拍」的 100 張 BMP,各自存到一個資料夾:

```
PSF_Fitting/quick_recalibration/validation_experiments/L1_precheck/
├── capture_01/                # 第一次重拍
│   ├── VisionTop_*_1.bmp      # 100 張(跟 setA/setB 來源同一個機型)
│   └── ...
├── capture_02/
└── capture_03/
```

### 跑 BADS

每次 capture 做兩件事:

1. **跑 setA 同樣 9 個 FOV × 15 trial**:這樣 capture_01/02/03 各產生一份「跟 setA 直接可比」的結果
2. (可選)**也跑 setB 同樣 9 個 FOV × 15 trial**:把 setB 也納入跨 capture 對比,雙重驗證

腳本架構:複製 `L0_repeat_fit/run_L0_repeat_fit.m`,改兩處:
- 輸入影像來源 from `Crop_circle_FreqFiltered/` 改成 `L1_precheck/capture_NN/`
- output_root 寫到 `L1_precheck/results/capture_NN_setA/`

預估時間:每組 9 FOV × 15 trial ≈ 80–90 分鐘。完整版本(3 capture × 1 set)= 4–4.5 hr 純 BADS;若兩 set 都做就翻倍。

### 跑分析

每組(capture × set 組合)用既有的 `deep_analyze_L0.py`(只要 SCRIPT_DIR 跟著新位置,腳本不用改)。然後寫一份新的跨 capture 對比腳本 `compare_l1_precheck.py`,要回答:

- 三次 capture 各自的主/次 basin 機率分別是多少?
- 這三個機率的標準差有多大?跟 setA/setB 跨 FOV 看到的 6% 差距相比,大還是小?
- reference basins 的位置(centroid)跨 capture 移動多少?跟 L0 看到的「basin 物理位置穩定」結論一致嗎?

---

## 判讀規則(明確 if-then)

跑完三次 capture 都用 setA 同樣 9 FOV 後:

| capture 之間的主 basin 機率變動範圍 | 判讀 | 對 Layer 1c 的影響 |
|---|---|---|
| ≤ 10 個百分點(例:65–75%) | 跨拍攝穩定 | Layer 1c 維持 advisory,設計不變 |
| 10–20 個百分點 | 不確定,需要更多 capture | 加跑 capture_04 之後再判 |
| > 20 個百分點 | 跨拍攝不穩定 | Layer 1c **必須升級** mandatory,reference basins 要按 capture 重算 |

判讀也要 cross-check **reference basin centroid 跨 capture 的距離**:如果 basin 中心本身偏移很大,代表「basin 物理意義」也跟拍攝噪聲耦合,不只是機率問題。

---

## 跟完整 L1 的差異

| 屬性 | 完整 L1(DESIGN §10.2) | 本前置版 |
|---|---|---|
| 拍攝次數 | 3 | 3(同) |
| 每次拍幾張 | 100 全 FOV | 100(同;但分析只用 9 個 FOV 子集) |
| 跑什麼 | Whole-FOV 100 fit | L0 風格 9 FOV × 15 trial |
| 時間 | 1.5–2 hr × 3 = 4.5–6 hr | 80–90 min × 3 = 4–4.5 hr |
| 回答的問題 | 拍攝噪聲 + 擬合噪聲 vs 機台真實變化 | **只**回答 basin 機率跨拍攝穩不穩 |

**重點**:本前置版**不取代**完整 L1。完整 L1 仍然要做,而且要按 DESIGN §10.2 的設計跑。前置版的角色是:在動完整 L1 之前先排除「Layer 1c 設計錯」的風險。

---

## 採納後處置

執行完本前置版後:

1. 在 [`validation_experiments/README_TW.md`](README_TW.md) 的進度看板加一列「L1 前置驗證」
2. 結論寫成 `validation_experiments/L1_precheck_results_TW.md`(canonical 報告)
3. 本檔(計畫)可刪除,或保留作為「為什麼這樣設計」的歷史紀錄
