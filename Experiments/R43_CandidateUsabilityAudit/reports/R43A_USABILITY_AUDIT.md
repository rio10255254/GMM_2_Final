# R43A Usability Audit — 近期候選堪用性分析

## 摘要

這份分析把 COMBO、已核准替代、R39、R40、R41、R42 的主要候選放到同一張表。目的不是重新訓練，而是回答一個實務問題：近期模型到底有沒有哪一些已經堪用。

結論很直接：**沒有任何新候選可以全面取代 COMBO；但不是全部都不能用。R39 a030 是目前最接近正式替代討論的候選，R40/R41/R42 則是顯微特徵與邊界重建的研究材料。**

2026-05-06 補上 R42 外部 GMF 後，R42 最好的外部候選仍在三個尺度都明顯退步：8px `+24.6%`、0.8px `+94.3%`、0.08px `+98.9%`。所以 R42 可以拿來看顯微邊界能力，但不適合拿去做正式量測。

## 完成標準

- 正式替代：外部三尺度守門不能明顯輸 COMBO。
- 顯微堪用：格線、缺陷、邊界或高頻細節要明顯比 COMBO 好。
- 實驗起點：即使不能部署，也要提供清楚能力來源。
- 不堪用：守住舊能力但沒有新能力，或新能力變好但失去太多舊守門且沒有明確用途。

## 核心排名

| Rank | 候選 | 類別 | 建議用途 | score | 判讀 |
|---:|---|---|---|---:|---|
| 1 | `R39 a030` | alternate_grade | 可列入替代候選討論 | 8.95 | 外部守門在可接受範圍內，且形狀泛化確實比 COMBO 好。 |
| 2 | `COMBO` | formal_baseline | 正式 baseline | 8.01 | 目前最均衡，仍是正式預設。 |
| 3 | `R42 combo latest` | specialist_research_use | 顯微重建研究或人工檢查用 | 7.39 | 顯微能力明顯變好，但舊守門失敗，不能當正式量測替代。 |
| 4 | `R42 r41 latest` | specialist_research_use | 顯微重建研究或人工檢查用 | 7.36 | 顯微能力明顯變好，但舊守門失敗，不能當正式量測替代。 |
| 5 | `R42 r41 best` | specialist_research_use | 顯微重建研究或人工檢查用 | 7.14 | 顯微能力明顯變好，但舊守門失敗，不能當正式量測替代。 |
| 6 | `R42 guarded KD probe` | specialist_research_use | 顯微重建研究或人工檢查用 | 7.07 | 顯微能力明顯變好，但舊守門失敗，不能當正式量測替代。 |
| 7 | `R42 combo best` | specialist_research_use | 顯微重建研究或人工檢查用 | 6.96 | 顯微能力明顯變好，但舊守門失敗，不能當正式量測替代。 |
| 8 | `R41 direct` | specialist_research_use | 顯微重建研究或人工檢查用 | 6.29 | 顯微能力明顯變好，但舊守門失敗，不能當正式量測替代。 |

分數只是排序輔助，不是升級標準。升級仍以正式外部守門為準。

## 正式替代視角

| 候選 | external 8px | vs COMBO | external 0.8px | vs COMBO | external 0.08px | vs COMBO | 判讀 |
|---|---:|---:|---:|---:|---:|---:|---|
| `R39 a030` | 0.1438 | -6.9% | 0.1400 | +6.4% | 0.0839 | -16.0% | PASS_TRADEOFF |
| `COMBO` | 0.1545 | +0.0% | 0.1316 | +0.0% | 0.0999 | +0.0% | PASS |
| `R42 combo latest` | 0.2862 | +85.3% | 0.2745 | +108.6% | 0.2517 | +152.0% | FAIL_8PX_0P8PX_0P08PX_REGRESSION |
| `R42 r41 latest` | 0.2799 | +81.1% | 0.2087 | +58.6% | 0.2257 | +126.0% | FAIL_8PX_0P8PX_0P08PX_REGRESSION |
| `R42 r41 best` | 0.1926 | +24.6% | 0.2557 | +94.3% | 0.1987 | +98.9% | FAIL_8PX_0P8PX_0P08PX_REGRESSION |
| `R33 robust p95` | 0.1533 | -0.8% | 0.1190 | -9.5% | 0.0863 | -13.6% | PASS |
| `R38v2 8px gate` | 0.1440 | -6.8% | 0.1342 | +2.0% | 0.1065 | +6.6% | PASS_TRADEOFF |
| `R40 a045` | 0.1898 | +22.8% | 0.1333 | +1.3% | 0.0970 | -2.8% | FAIL_8PX_REGRESSION |

正式替代面最有價值的是 `R39 a030`。它不是完美：0.8px 比 COMBO 退步約 6.4%。但它 8px 與 0.08px 都比 COMBO 好，而且外部結果在替代候選容忍帶內。R40 a045 的顯微能力雖然好，外部 8px 退步太大；R42 補測後確認三尺度都退步，不能當正式替代。

## 顯微與邊界能力

| 候選 | shape PSNR | micro PSNR | micro HF | boundary PSNR | boundary dist | boundary F1 | local ring | 建議用途 |
|---|---:|---:|---:|---:|---:|---:|---|---|
| `R39 a030` | 25.0326 | 25.0323 | 0.2206 | 22.9994 | 7.2536 | 0.7022 | PASS | 可列入替代候選討論 |
| `COMBO` | 22.8411 | 22.7326 | 0.2234 | 20.5524 | 7.8241 | 0.6260 | PASS | 正式 baseline |
| `R42 combo latest` | — | — | — | 34.0902 | 3.4777 | 0.8680 | FAIL_8px_0p8px_0p08px | 顯微重建研究或人工檢查用 |
| `R42 r41 latest` | — | — | — | 34.1781 | 3.6026 | 0.8690 | FAIL_8px_0p8px_0p08px | 顯微重建研究或人工檢查用 |
| `R42 r41 best` | — | — | — | 32.8891 | 3.4834 | 0.8727 | FAIL_8px_0p8px_0p08px | 顯微重建研究或人工檢查用 |
| `R42 guarded KD probe` | — | — | — | 32.6607 | 3.5353 | 0.8705 | FAIL_8px_0p8px_0p08px | 顯微重建研究或人工檢查用 |
| `R42 combo best` | — | — | — | 31.8141 | 3.3485 | 0.8727 | FAIL_8px_0p8px_0p08px | 顯微重建研究或人工檢查用 |
| `R41 direct` | — | 29.4556 | 0.7241 | 22.7312 | 5.0401 | 0.7323 | FAIL_8px_0p8px_0p08px | 顯微重建研究或人工檢查用 |
| `R40 a045` | — | 26.8911 | 0.3414 | 23.3481 | 6.7679 | 0.7244 | FAIL_8px | 顯微重建研究或人工檢查用 |
| `R42 low alpha a003` | — | — | — | 20.8252 | 7.5293 | 0.6420 | PASS | 不建議使用 |
| `R42 low alpha a001` | — | — | — | 20.6423 | 7.6609 | 0.6310 | PASS | 不建議使用 |
| `R41 a050` | — | 26.6662 | 0.3358 | — | — | — | FAIL_8px_0p08px | 顯微重建研究或人工檢查用 |
| `R41 a045` | — | 26.1840 | 0.3012 | — | — | — | FAIL_8px_0p08px | 顯微重建研究或人工檢查用 |
| `R42 low alpha a005` | — | — | — | 21.0094 | 7.5402 | 0.6518 | FAIL_8px_0p08px | 不建議使用 |
| `R42 low alpha a002` | — | — | — | 20.7337 | 7.5530 | 0.6368 | FAIL_8px | 不建議使用 |

- 形狀泛化最好的是 `R39 a030`，shape PSNR `25.0326`。
- R40/R41 顯微特徵測試中，最高 micro PSNR 是 `R41 direct`，micro PSNR `29.4556`。
- R42 邊界測試中，最高 boundary PSNR 是 `R42 r41 latest`；邊界位置最穩的是 `R42 combo best`，距離 `3.3485` px。

## 堪用性判斷

### 可以拿來正式討論

- `R39 a030`：目前最像「可升級替代」的近期候選。適合想要形狀泛化，同時重視 8px 與 0.08px 的場景；如果主戰場是 0.8px，仍應優先用 COMBO 或 R33。

### 可以拿來顯微研究或人工檢查

- `R42 combo latest`：顯微能力明顯變好，但舊守門失敗，不能當正式量測替代。
- `R42 r41 latest`：顯微能力明顯變好，但舊守門失敗，不能當正式量測替代。
- `R42 r41 best`：顯微能力明顯變好，但舊守門失敗，不能當正式量測替代。
- `R42 guarded KD probe`：顯微能力明顯變好，但舊守門失敗，不能當正式量測替代。
- `R42 combo best`：顯微能力明顯變好，但舊守門失敗，不能當正式量測替代。
- `R41 direct`：顯微能力明顯變好，但舊守門失敗，不能當正式量測替代。
- `R40 a045`：顯微能力明顯變好，但舊守門失敗，不能當正式量測替代。
- `R41 a050`：顯微能力明顯變好，但舊守門失敗，不能當正式量測替代。
- `R41 a045`：顯微能力明顯變好，但舊守門失敗，不能當正式量測替代。

這些候選不是不能用，而是不能拿來直接取代正式量測流程。它們比較適合作為顯微結構重建、人工檢查、下一輪訓練起點。

### 暫時不值得用

- `R42 low alpha a003`：守住舊能力，但新能力提升太小，沒有實際替換價值。
- `R42 low alpha a001`：守住舊能力，但新能力提升太小，沒有實際替換價值。
- `R42 low alpha a005`：沒有形成清楚可用價值。
- `R42 low alpha a002`：沒有形成清楚可用價值。

低比例混合版特別值得注意：它們接近守住舊環形，但顯微邊界能力幾乎還停在 COMBO 附近，所以不是好折衷。

## 肉眼檢查圖

R43 另外整理了三張代表圖，方便直接比較顯微特徵和邊界重建質感。

- 顯微特徵總覽：`Experiments/R43_CandidateUsabilityAudit/results/visual_review/micro_feature_visual_sheet.png`
- 邊界特徵總覽：`Experiments/R43_CandidateUsabilityAudit/results/visual_review/boundary_feature_visual_sheet.png`
- 邊界局部放大：`Experiments/R43_CandidateUsabilityAudit/results/visual_review/boundary_zoom_visual_sheet.png`

肉眼判讀和數字一致：R42 的邊界、缺陷和局部細節最清楚，但連續量測穩定性不足；R40/R41 比 COMBO 更有顯微細節能力，但還不夠穩；R39 a030 是目前最平衡的近期候選。

## 深層判讀

R39 到 R42 的共同現象是：模型不是沒有能力重建顯微結構，而是能力被推高時，舊的連續量測守門會掉。這代表問題不只是「影像清不清楚」，而是「同一個結構在連續位移時，輸出位置有沒有跟著真實位置穩定移動」。

因此，下一步不應再只做更多資料混合、低 alpha 平均或靜態老師牽引。更該做的是已知位移測試：同一條線、同一組格線、同一個缺陷，在 0.08px、0.8px、8px 或其他小位移下，模型輸出的邊界位置是否同步移動。這會比單張 PSNR 或單張 boundary F1 更接近你真正關心的能力。

## 結論

- **正式預設仍是 COMBO。**
- **最堪用的近期替代候選是 R39 a030。** 它可以進入 owner 決策，但不是無條件取代 COMBO。
- **顯微重建最有價值的是 R42 full endpoints。** 它們對邊界、格線、缺陷的能力是真實的，但外部補測後確認不適合直接進正式量測。
- **R40/R41 是能力來源。** 它們證明顯微細節可以被學到，但目前不該部署。
- **低 alpha 折衷目前沒有價值。** 它守住舊能力的同時，也幾乎放棄了新能力。

## 產物

- JSON scorecard：`Experiments/R43_CandidateUsabilityAudit/results/candidate_usability/usability_scorecard.json`
- CSV scorecard：`Experiments/R43_CandidateUsabilityAudit/results/candidate_usability/usability_scorecard.csv`
- 視覺檢查圖：`Experiments/R43_CandidateUsabilityAudit/results/visual_review/`
