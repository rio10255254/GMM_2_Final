# Visual vs Metric Decoupling / 視覺-量測解耦現象的系統性實證

Last updated: 2026-05-26
狀態:**DESIGN(等使用者拍板候選清單跟指標選擇)**

## 為什麼這個分析存在

論文最直接、最容易溝通的發現是:**影像視覺銳利度跟下游量測穩定度是解耦的——同樣的 GMF 改善可以伴隨視覺變軟(R33)也可以伴隨視覺變銳(COMBO);同樣的視覺主場大贏也可能伴隨 GMF 崩潰(R46)**。

這個發現在專案歷程裡已經由一系列實驗證實,但**從來沒有被整合成一張「sharpness × stability」平面圖**。各候選的視覺指標跟 GMF 結果散在 `PROJECT_STATE.md`、各 `Experiments/R##_*/reports/` 跟 `ESTIMATOR_POLICY.json` 裡,讀者要一輪一輪查才能拼出全貌。

這個補測的單一輸出是:**把所有關鍵候選畫在同一張 (視覺軸, 量測軸) 平面上**,讓讀者一眼看出四個象限都有真實 model,證明兩軸是解耦的。

## 對應論文段落

主要對應:**論文第 6 章開場 hero figure**(目前論文未寫,但 4.8 已經為此預留分析框架)

次要對應:
- 1.3 貢獻一(MOSR 框架):這張圖是 MOSR 必要性的最直接視覺證據
- 4.6.1「打破權衡」:這張圖同時是「權衡可被選擇性打破」的證據(COMBO 同時拿到銳跟穩),也是「打破有上限」的證據(R46 越界就崩)
- 4.8.3 邊界寬度一致性 μ_w / CV_w 分析的前置(σ̂ 跟 μ_w 在這張圖各佔一軸)

## 候選清單(待 review)

| Tag | 模型名 | 角色 | 預期所在象限 |
|---|---|---|---|
| R30 | `r30_b1_dironly` | former baseline | 視覺強 / 量測中(右上偏右) |
| R33 | `r33_robust_p95` | GMF extreme alternate | 視覺軟 / 量測極好(左上) |
| R38v2 | `r38v2_8px_gate` | visual priority alternate | 視覺強 / 量測好(右上) |
| **COMBO** | `r38v2_8px_gate_p95` | **formal baseline** | 視覺強 / 量測好(右上,接近 R38v2) |
| a030 | `r39_combo_strong_avg_a030` | alternate-grade pending | 視覺中強 / 量測好(右上) |
| **a025** | `r39r40_complementary_avg_a025` | **approved alternate 2026-05-11** | 視覺中強 / 量測好(右上,首個三尺度全過 3% 上限) |
| R40 a045 | `r40_combo_best_avg_a045` | research-only(顯微強但 8px 退) | 視覺強 / 量測 8px 差(混合) |
| R42 r41_best | `r42_r41_best` | research-only(邊界強但 GMF 全退) | 視覺強 / 量測全退(左下) |
| R46 | `r46_a025_corner_finetune` | research-only(主場贏 ring 崩) | 視覺極強 / 量測極差(右下) |

**沒納入的候選**:
- R44 全系列、R45 全系列:**沒有外部 GMF 結果**(都被判 research-only 沒送外部),無法在量測軸定位
- R41 全系列:同上(訓練完沒送外部)
- R31 三候選、R32:可以納入,但都是「兩軸都差」的退步點,放不放看密度

## 兩軸定義(待 review)

### 視覺軸候選

| 候選指標 | 來源 | 已現成的候選數 |
|---|---|---|
| **`edge_steepness_p95` vs R30 (%)** | PROJECT_STATE 已用,R39 a025 capability_eval 有 csv | R30 / R33 / R38v2 / COMBO / a025 / a030 / a043 已有,其他需補算 |
| `gradient_magnitude_mean` vs R30 (%) | 同上 | 同上 |
| `contrast_std` vs R30 (%) | 同上 | 同上 |
| 邊界寬度 μ_w (絕對值, μm) | 論文 4.8.3 定義,**目前沒腳本算** | 需從 GT vs recon 對所有候選新算 |

**建議主軸用 `edge_steepness_p95 vs R30 (%)`**,理由:
- 它已被 PROJECT_STATE 跟 ESTIMATOR_POLICY.json 廣泛使用,讀者熟悉
- COMBO +89% / R33 -22% 數字漂亮、區別大
- 不需要重新算大部分候選,可以最快做出 v1 圖

但**邊界寬度 μ_w 才是論文 4.8.3 設計的正式視覺指標**,如果想完全跟論文 4.8 對齊,這個一定要補算。建議先用 edge_steepness 出 v1,確定圖長相 OK,再花時間補 μ_w 做 v2。

### 量測軸候選

| 候選指標 | 來源 | 備註 |
|---|---|---|
| **`external GMF 0.8px step_std`** | 各 `external_compare_summary.json` | 論文「主戰場」,首選 |
| `external GMF 8px step_std` | 同上 | 大尺度宏觀守門 |
| `external GMF 0.08px step_std` | 同上 | 小尺度精細 |

**建議主軸用 `external GMF 0.8px step_std`**,理由:它是論文跟 ESTIMATOR_POLICY 的「主戰場」單一指標,容易溝通。8px 跟 0.08px 同時做為色階或大小,把「三尺度同時呈現」這件事壓進同一張圖。

## 資料來源 path 表

| Tag | external GMF JSON | 視覺指標來源 |
|---|---|---|
| R30 | `Traing_Progress/organized_20260316/round30/gmf_results/raw/r30_b1_dironly/pitch*/GMF_score.txt`(需自己 parse) | (基準,定義為 0) |
| R33 | `Experiments/R33RobustLoss/results/external_gmf/pitch*/GMF_score.txt` | PROJECT_STATE table |
| R38v2 | `Experiments/R38v2SeqFixed/results/external_gmf/pitch*/GMF_score.txt` | PROJECT_STATE table |
| COMBO | `Experiments/R38v2SeqFixed/results/external_gmf_combo/pitch*/GMF_score.txt` | PROJECT_STATE table |
| a030 | `Experiments/R39_ShapeGeneralization/results/external_gmf_a030/external_compare_summary.json` | `R39_RESULTS.md` visual profile |
| a025 | `Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/external_recon/a025/external_compare_summary.json` | `R39_ShapeGeneralization/results/a030_x_a043_sweep/capability_eval/visual_stats.csv` |
| R40 a045 | `Experiments/R40_MicroscopyFeatureCoverage/results/external_gmf/external_compare_summary.json` | `R40_RESULTS.md` |
| R42 r41_best | `Experiments/R42_MicroscopyBoundaryFidelity/results/external_gmf/...`(需確認) | `R42_RESULTS.md` |
| R46 | `Experiments/R46_CornerAwareFineTune/results/external_gmf/external_compare_summary.json` | `R46_RESULTS.md` |

**注意**:各候選的視覺指標**不一定都用同一張資料、同一個計算口徑**算出來。R33 / R38v2 / COMBO 在 PROJECT_STATE 的數字是 vs R30,a025 capability_eval 的 visual_stats.csv 是 frame-wise mean 在 ring 三尺度上算。**腳本必須先統一資料集跟口徑再算**,不能直接拼現成數字。

## 預期輸出

1. **主圖**:`results/visual_metric_decoupling_scatter.png` — 四象限散佈圖
   - X 軸:edge_steepness_p95 vs R30 (%)
   - Y 軸:external GMF 0.8px step_std(越低越好)
   - 點大小:用 8px 或 0.08px 結果做尺寸(可選)
   - 點顏色:用「外部 GMF verdict」分(PASS_UPGRADE_GUARD / TRADEOFF_OK / REGRESSED)
   - 標註:每個點旁邊標 tag 名(R30/R33/COMBO/a025/R46...)

2. **跨候選統計表**:`results/decoupling_table.csv` + `results/decoupling_table.md`
   - 一行一個候選
   - 欄位:tag / 視覺軸數字 / 量測軸三尺度 / verdict / 預期所在象限

3. **報告**:`reports/decoupling_evidence.md`
   - 圖嵌入 + 表
   - 文字解讀:四個象限分別有哪些候選、這證明了什麼
   - 對應論文段:可直接搬到論文第 6 章開場

## Open Questions(等使用者拍板)

1. **候選清單**:上面列了 9 個候選。要不要加 R31/R32 等已關閉退步點當「兩軸都差」的對照?還是太雜?
2. **視覺主軸**:用 edge_steepness_p95 vs R30(快、現成、論文 4.8 沒明說用這個)還是補算邊界寬度 μ_w(慢、要新做、跟論文 4.8.3 直接對應)?
3. **量測軸呈現**:三尺度都進主圖(點大小/顏色編碼),還是主圖只用 0.8px、其他兩尺度進補充表?
4. **R42 取哪個 candidate**:R42 有 4 個 candidate(combo_best / combo_latest / r41_best / r41_latest)。要不要全進去,還是只取 r41_best(R42 中外部最好的)?

回答完這四個問題,我就可以動 `scripts/decoupling_scatter.py`。
