# σ̂ + b Decomposition / 隨機分量與系統性偏差分解

Last updated: 2026-05-26
狀態:**SCRIPT_DRAFT(README 完成,腳本待寫)**

## 這個分析在驗證什麼

論文核心 main claim:**「神經重建在精密位移量測情境下的本質作用是誤差型態轉換器——把隨機誤差重新分配為可追蹤的結構性偏差」**

這個 main claim 要可信,必須證明兩件事**同時成立**:

- **C1**:隨機分量 σ̂ 隨訓練目標優化而下降
- **C2**:系統性分量 b 出現且**跨幀穩定**(不是隨機飄移)

如果只有 σ̂ 下降、b 也跟著下降 → 那是「整體誤差變小」,不是「型態轉換」(N2 推翻)
如果 σ̂ 下降但 b 不穩定 → 那是「隨機誤差換成另一種隨機誤差」,沒有結構化(N3 推翻)
如果 σ̂ 不下降 → 「轉換」前提不成立,根本沒在優化隨機分量(N1 推翻)

**這個分析的結果直接決定整篇論文 main claim 能否成立。**

如果 C1+C2 都成立 → main claim 站得住,後續 C3/C4/C5 補測有意義,1-4 章按金字塔結構重組
如果 N1/N2/N3 任一發生 → main claim 不成立,**論文主軸必須重想**,前面討論的金字塔結構全部作廢

## 對應論文段落

- **論文 4.8.1**(逐幀步進統計量之分解):這節定義了 σ̂ 跟 b,但目前是 design,沒實證
- **論文 1.3 貢獻二**(誤差型態轉換):這個分析是貢獻二的核心證據
- **論文 4.6**(多幀序列一致性):如果 C1+C2 成立,4.6 的論述要改寫成「多幀一致性提供分離 σ̂ 跟 b 的監督訊號」

## 量化定義

### 從原始資料到 σ̂ / b

每個候選 × 每個 pitch 尺度(8px / 0.8px / 0.08px),從 `GMF_score.txt` parse 出位置序列:

```
PosY_i (i = 0, ..., N-1)    # 從 GMF 工具回傳的 Y 軸定位
step_i = PosY_{i+1} - PosY_i  (i = 0, ..., N-2)   # 逐幀位移估測
```

注意符號:現有 `external_compare_summary.json` 的 `median_step` 多為負值(例如 0.8px pitch 為 −0.798),代表 PosY 是遞減方向。**統一以 |step_i| 跟 expected_step_px 比較**,符號不影響 σ̂ 與 b 的相對結構。

### 三個核心量

```
μ̂ = mean(|step_i|)              # 樣本平均位移(估測中心)
σ̂ = std(|step_i|, ddof=1)       # 樣本標準差(隨機分量)
s* = expected_step_px            # 真值步進(已知 nominal pitch)
b = μ̂ − s*                      # 系統性偏差(可正可負)
```

### 跨幀穩定度(C2 用)

C2 要求「b 跨幀穩定」,而 b 本身是序列的單一統計量。實際上 C2 的意涵是:**估測序列偏離真值的方向應該結構化**——也就是 step_i − s\* 的分布要有結構,而不是純隨機。

操作化定義:**對 (step_i − s\*) 序列做 lag-1 自相關**。
- |lag-1 autocorr| > 0.3 → 序列有結構(C2 支持)
- |lag-1 autocorr| ≈ 0 → 序列是白噪聲(C2 推翻,跟 σ̂ 同質)

注意:`external_compare_summary.json` 已存的 `lag1_autocorr_0p8px` 是 step_i 本身的自相關,可以重用,但需確認是否扣除真值後的自相關。腳本以扣除真值後的版本為主。

## 候選清單

第一輪先跑「主軸論述歷程」的四個關鍵點:

| Tag | 模型 | 在主軸論述中的角色 |
|---|---|---|
| **R30** | `r30_b1_dironly` | 主軸起點(前任 baseline,假設誤差仍以隨機為主) |
| **R33** | `r33_robust_p95` | 視覺退讓但 GMF 極好(假設轉換已部分發生) |
| **R38v2** | `r38v2_8px_gate` | 視覺保留且 GMF 好(假設轉換以另一種方式發生) |
| **COMBO** | `r38v2_8px_gate_p95` | 三方面最均衡(假設轉換最完整) |

C1+C2 成立的條件:**σ̂ 從 R30 → R33/R38v2 → COMBO 單調下降,b 跨候選都顯示結構化(lag-1 autocorr 顯著非零)**。

第二輪(如果 C1+C2 成立)再加 a030 / a025 / R40 a045 / R42 r41_best / R46 等後續候選,看主軸是否延伸到後續歷程。

## 三尺度全部算

論文 4.8 是用單一尺度設計,但 external GMF 有三尺度(8px / 0.8px / 0.08px),三尺度都跑可以多一層證據:

- **0.8px 是「主戰場」** — 論文跟 ESTIMATOR_POLICY 主指標,C1+C2 必須在這個尺度上成立
- **8px 是宏觀守門** — 大尺度位置追蹤,跟 0.8px 主戰場有共通結構
- **0.08px 是精細尺度** — 接近系統雜訊極限,可能呈現 σ̂ 已逼近 CRB 的早期訊號

如果 C1+C2 在三尺度都成立 → 強證據
如果只在 0.8px 主戰場成立 → 中等證據(可解釋,但要寫清楚為何其他尺度不同)
如果三尺度都不成立 → 弱證據,N1/N2/N3 推翻

## 資料來源

| Tag | GMF_score.txt path 樣板 |
|---|---|
| R30 | `Traing_Progress/organized_20260316/round30/gmf_results/raw/r30_b1_dironly/pitch{8px,0p8px,0p08px}/GMF_score.txt` |
| R33 | `Experiments/R33RobustLoss/results/external_gmf/pitch{8px,0p8px,0p08px}/GMF_score.txt` |
| R38v2 | `Experiments/R38v2SeqFixed/results/external_gmf/pitch{8px,0p8px,0p08px}/GMF_score.txt` |
| COMBO | `Experiments/R38v2SeqFixed/results/external_gmf_combo/pitch{8px,0p8px,0p08px}/GMF_score.txt` |

每尺度的 `expected_step_px` 直接從現有 `external_compare_summary.json` 拿(R33/R38v2/COMBO 有,R30 要從上層補)。

## 預期輸出

1. **趨勢圖**:`results/sigma_b_trend.png`
   - 兩個 panel(σ̂ vs candidate / b vs candidate)
   - 每個 panel 三條線(8px / 0.8px / 0.08px)
   - X 軸候選依時間排序:R30 → R33 / R38v2 → COMBO

2. **跨候選統計表**:`results/sigma_b_table.csv` + `results/sigma_b_table.md`
   - 一行一個 (candidate, scale) 組合
   - 欄位:tag / scale / N / μ̂ / σ̂ / s* / b / b/s* (%) / lag1_autocorr(step−s\*) / verdict

3. **逐候選自相關圖**:`results/lag1_autocorr_panel.png`
   - 每個候選 × 每個尺度的 (step − s*) 散佈圖 + lag-1 散佈
   - 視覺檢查 b 結構化是否真實

4. **C1+C2 驗證報告**:`reports/c1_c2_verification.md`
   - 數據表 + 趨勢圖嵌入
   - **明確判定**:C1 通過/失敗、C2 通過/失敗、整體 verdict
   - 如果失敗,記錄是 N1/N2/N3 哪一種,以及對論文主軸的意涵

## C1+C2 的 falsification criterion(明確判準)

**C1 通過**:
- 0.8px 主戰場:σ̂(COMBO) < σ̂(R30) 且降幅 > 10%(否則屬於量測噪聲)
- 8px:σ̂(COMBO) ≤ σ̂(R30)(允許持平,但不能變差)
- 0.08px:σ̂(COMBO) < σ̂(R30) 且降幅 > 10%

**C2 通過**:
- 0.8px 主戰場:R30/R33/R38v2/COMBO 四個候選的 (step − s*) lag-1 autocorr 絕對值都 > 0.3
- 三尺度至少兩尺度 lag-1 autocorr > 0.3 在所有候選上成立

**N1 推翻**(σ̂ 不下降):
- 0.8px:σ̂(COMBO) ≥ σ̂(R30) 或 降幅 < 5%

**N2 推翻**(σ̂ 跟 b 同向下降):
- 三個尺度都顯示 b 的絕對值從 R30 → COMBO 單調下降(代表這只是「整體誤差變小」)

**N3 推翻**(b 不穩定):
- lag-1 autocorr 在多數候選上 < 0.2(代表 step − s\* 接近白噪聲)

**部分支持**(主軸要修正但不完全推翻):
- 0.8px 主戰場通過 C1+C2,但 8px 或 0.08px 沒通過 → 主軸仍可寫,但要明確說明只在「主戰場尺度」成立
- C1 通過但 C2 邊界(lag-1 ≈ 0.2-0.3) → 寫成「型態轉換有初步證據,但結構化程度有限」

## Open Questions(腳本動之前的最後確認)

1. **PosX vs PosY 哪個是位移軸**:從前面 GMF_score.txt 樣本看,PosX ≈ 752.5 變化極小(±0.3),PosY 從 781.9 一路降到 ~730(60 幀 ~50 變化,單幀 ~0.8 ≈ pitch),所以**用 PosY 作為位移軸**。但 8px 序列的 PosY 變化可能跨更大範圍,要在腳本裡 sanity-check。

2. **R30 的 `expected_step_px` 從哪取**:R30 的 external_compare_summary.json 沒在 round30 目錄底下(前面 ls 沒看到),要從 R33/R38v2/COMBO 的同 pitch 取(三個應該都用同一份 reference 圖,所以 expected_step_px 應該一樣)。腳本實作時用 0.8px pitch 對應 `expected_step_px = 0.8`,其他類推。

3. **outlier filter 要不要做**:現有 external_compare_summary.json 用 `|z| > 5` 但所有候選 n_outliers 都是 0(沒實際移除任何點)。**腳本不做 outlier filter**,保留 raw step_std,跟現有方法論一致(`docs/operations/STARTING_NEW_EXPERIMENT.md` 第 6 條:External GMF 用 raw step_std,no outlier removal except z > 5)。

這三個問題我都先預設答案(用 PosY、用 nominal expected_step_px、不做 outlier filter),如果你 OK 我直接動腳本。
