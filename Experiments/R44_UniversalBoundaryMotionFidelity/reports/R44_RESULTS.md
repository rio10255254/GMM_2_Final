# R44 結果 — 通用顯微邊界位移忠實度

## 摘要

R44 的目標是接在 R42 後面，從「單張顯微邊界清楚」推進到「同一個顯微結構在已知位移下，邊界位置要忠實跟著移動」。

目前狀態：**R44A 診斷完成，R44B 三個候選完成 24 epoch 訓練與位移測試；R44C 三個小型探針也已完成。研究上有進展，但仍未找到可直接升級或可直接堪用的平衡模型。**

最重要結論：

- R44A 顯示，R42 主要邊界候選已是近期最好的通用位移起點。
- R44B `r44_motion_from_r42_best` 進一步把整體位移誤差從 R42 的 `0.4609 px` 降到 `0.3813 px`，格線位移誤差從 `2.7911 px` 降到 `2.2457 px`。
- 但 R44B 主候選的整體邊界距離從 R42 的 `3.6726 px` 小幅變差到 `3.7276 px`，主要退在大區塊與混合場景。
- 本地三尺度環形代理測試退步明顯：8px `+45.1%`、0.8px `+46.7%`、0.08px `+32.3%` vs COMBO 本地參考。因此 R44B 主候選是研究成功的材料，不是量測替代候選。
- R44C 顯示：單純降低 motion 強度或把大區塊/混合場景排除在 motion 之外，都不能真正解決問題。最佳探針 `r44c_static_heavy_all_motion` 比 R44B 稍微保住整體邊界與混合場景，但位移與格線優勢也被拉回，仍不可升級。

## 子報告導航

R44 是多階段研究，本主報告吸收各階段精華；下表對應到每階段的 canonical 子報告。重新執行或更新時，請先改子報告，再同步本主報告：

| 階段 | 子報告 | 重點 |
|---|---|---|
| R44C 探針計畫 | [`R44C_PROBE_PLAN.md`](R44C_PROBE_PLAN.md) | 三個探針設計、完成標準與判定方式 |
| R44D 分族診斷 | [`R44D_FAMILY_DIAGNOSTIC.md`](R44D_FAMILY_DIAGNOSTIC.md) | 結構類型、位移段與指標有效性 |
| R44E 專項探針 | [`R44E_TARGETED_PROBE.md`](R44E_TARGETED_PROBE.md) | 大區塊/混合場景短訓練修補與否定結論 |
| R44F 錯誤解剖 | [`R44F_ERROR_DIAGNOSTIC.md`](R44F_ERROR_DIAGNOSTIC.md) | 指標壓力測試與錯誤案例挑選 |
| R44G 邊界形狀體檢 | [`R44G_BOUNDARY_SHAPE_METRICS.md`](R44G_BOUNDARY_SHAPE_METRICS.md) | 厚度、破碎、直邊、角點分項排名 |
| R44H Step A | [`R44H_STEPA_FAMILY_AVERAGE.md`](R44H_STEPA_FAMILY_AVERAGE.md) | R44C 乾淨度檢查與 R44B 家族權重平均 |
| R44H Step B 計畫 | [`R44H_STEPB_REGION_KD_PLAN.md`](R44H_STEPB_REGION_KD_PLAN.md) | 局部老師蒸餾的 go/no-go 門檻 |
| R44H Step B 結果 | [`R44H_STEPB_REGION_KD.md`](R44H_STEPB_REGION_KD.md) | 概念驗證失敗紀錄 |
| 外部 GMF 紀錄 | [`R44_EXTERNAL_COMPARE.md`](R44_EXTERNAL_COMPARE.md) | R44 暫不送外部，僅作紀錄 |
| 文件追溯稽核 | [`R44_HISTORY_TRACEABILITY_AUDIT.md`](R44_HISTORY_TRACEABILITY_AUDIT.md) | R39-R44H 文件結構稽核 |

## 實驗定位

- 正式基準：COMBO。
- 比較對象：COMBO、R39 a030、R40 a045、R41、R42 主要候選。
- R44 第一版：研究優先，不作為預設升級候選。
- 外部 GMF：只作舊能力紀錄，不作 R44 研究淘汰線；本輪尚未送外部 GMF。

## 資料與執行

R44 新增七類已知位移顯微結構序列：

| stage | 類型 | 檢查重點 |
|---|---|---|
| `stage_41_motion_lines` | 細線 | 細線位移是否忠實 |
| `stage_42_motion_grids` | 格線 | pitch / phase 是否跟著位移 |
| `stage_43_motion_junctions` | 交叉線 | 交會點是否漂移 |
| `stage_44_motion_curves` | 曲線 | 曲線邊界是否穩定 |
| `stage_45_motion_regions` | 大區塊 | 邊界是否跟錯或變形 |
| `stage_46_motion_defects` | 缺陷 | 小缺陷位置是否漂移 |
| `stage_47_motion_mixed` | 混合場景 | 大形狀與小細節是否同時忠實 |

每個序列包含 `0 / 0.08 / 0.16 / 0.4 / 0.8 / 2 / 8 px` 位移幀，並為每幀產生來源圖、答案圖、邊界遮罩、中心線遮罩、距離圖與 metadata。

實際資料包：

| 資料包 | 數量 | 位置 |
|---|---:|---|
| R44 motion train | 3920 frames | `Training_Data/r44_universal_boundary_motion/r44_motion_research_train/` |
| R44 motion validation | 980 frames | `Training_Data/r44_universal_boundary_motion/motion_val_unseen/` |
| 幾何標註 | 700 sequences | `Training_Data/r44_motion_geometry/` |

## R44A 既有模型診斷

數字越低越好。

| 模型 | 整體位移誤差 px | 整體邊界距離 px | 格線位移誤差 px | 細線邊界距離 px | 大區塊邊界距離 px | 混合場景邊界距離 px |
|---|---:|---:|---:|---:|---:|---:|
| COMBO | 0.8253 | 9.8284 | 5.3567 | 11.8781 | 11.3297 | 13.7947 |
| R39 a030 | 1.0481 | 8.1015 | 6.9042 | 11.0900 | 8.2230 | 10.0998 |
| R40 a045 | 1.3904 | 7.0905 | 9.3451 | 10.1631 | 6.3921 | 9.3964 |
| R41 direct | 1.4543 | 5.5602 | 9.6433 | 8.2668 | 4.9915 | 6.3884 |
| R42 best | 0.4609 | 3.6726 | 2.7911 | 2.4190 | 7.3401 | 6.6915 |

R44A 判讀：

- COMBO 對非週期結構的整體位移向量不算失控，但邊界距離偏大，代表它不是通用顯微邊界重建的最佳起點。
- R40 / R41 的邊界更靠近答案，但格線位移誤差非常大，顯示「單張更銳」不等於「週期結構位移忠實」。
- R42 是最好的整體起點：位移誤差最低、格線錯誤最低、細線與交叉線邊界明顯更準；但大區塊與混合場景仍是弱點。

## R44B 訓練結果

三個候選皆完成 24 epoch、每 epoch 160 train batches：

| 候選 | 起點 | checkpoint |
|---|---|---|
| `r44_motion_from_r42_best` | R42 `r42_boundary_from_r41` | `Traing_Progress/training_progress_GESR_v1_v5_ST0p8_SWP_r44_motion_from_r42_best_20260506_201801/weights/best_tradeoff.pth.tar` |
| `r44_motion_from_r40_a045` | R40 a045 | `Traing_Progress/training_progress_GESR_v1_v5_ST0p8_SWP_r44_motion_from_r40_a045_20260506_203143/weights/best_tradeoff.pth.tar` |
| `r44_motion_from_combo` | COMBO | `Traing_Progress/training_progress_GESR_v1_v5_ST0p8_SWP_r44_motion_from_combo_20260506_204231/weights/best_tradeoff.pth.tar` |

R44A + R44B 總表：

| 模型 | 整體位移誤差 px | 整體邊界距離 px | 格線位移誤差 px | 細線邊界距離 px | 大區塊邊界距離 px | 混合場景邊界距離 px |
|---|---:|---:|---:|---:|---:|---:|
| R44B from R42 | **0.3813** | 3.7276 | **2.2457** | **2.3368** | 7.5878 | 6.9202 |
| R42 best | 0.4609 | **3.6726** | 2.7911 | 2.4190 | 7.3401 | 6.6915 |
| R44B from COMBO | 0.5313 | 3.9081 | 3.2741 | 2.9714 | **5.9436** | 6.9901 |
| COMBO | 0.8253 | 9.8284 | 5.3567 | 11.8781 | 11.3297 | 13.7947 |
| R44B from R40 | 0.9087 | 3.7808 | 5.9051 | 2.9695 | 6.9774 | **5.9151** |
| R39 a030 | 1.0481 | 8.1015 | 6.9042 | 11.0900 | 8.2230 | 10.0998 |
| R40 a045 | 1.3904 | 7.0905 | 9.3451 | 10.1631 | 6.3921 | 9.3964 |
| R41 direct | 1.4543 | 5.5602 | 9.6433 | 8.2668 | 4.9915 | 6.3884 |

R44B 判讀：

- 主候選 `R44B from R42` 是目前最好的通用位移忠實候選：整體位移誤差與格線位移誤差都是最低。
- 它不是全面勝過 R42：整體邊界距離、大區塊與混合場景略退，代表 motion loss 有推動位移一致性，但還沒有同時保住所有靜態邊界品質。
- `R44B from COMBO` 對大區塊最好，且相較原始 COMBO 是巨大改善，但整體仍不如 R42 起點。
- `R44B from R40` 對混合場景邊界距離最好，但格線位移仍偏差，不能當主候選。

## 本地環形代理紀錄

本輪只對目前最有研究價值的 `R44B from R42` 補本地三尺度環形紀錄。這不是 R44 研究淘汰線，但可用來判斷舊代理能力退多少。

| 尺度 | R44B internal step std y | COMBO internal step std y | 相對 COMBO |
|---|---:|---:|---:|
| 8px | 0.2015 | 0.1389 | +45.1% |
| 0.8px | 0.2214 | 0.1509 | +46.7% |
| 0.08px | 0.1568 | 0.1185 | +32.3% |

判讀：R44B 主候選在通用顯微位移上有研究進展，但本地環形舊代理能力明顯退步；若要考慮量測替代，必須另開回收策略，不能直接升級。

## R44C 探針結果

R44C 是 R44 內部追加探針，不是新的正式實驗線。目的不是產生升級候選，而是快速檢查 R44B 的問題是否只是「motion 力道太強」或「某些結構不適合 motion loss」。

三個探針皆從 R42 最佳顯微邊界起點出發，完成 21 epoch、每 epoch 80 train batches 的短訓練：

| 探針 | 設計 | 判讀 |
|---|---|---|
| `r44c_low_motion_static_guard` | 降低 motion 強度，提高靜態邊界保護 | 不足以救回整體平衡；位移退回一些，邊界沒有明顯變好 |
| `r44c_family_holdout_motion` | 大區塊與混合場景不套 motion，只保留靜態邊界保護 | 無效；排除後大區塊/混合場景沒有被救回，格線與整體位移反而退更多 |
| `r44c_static_heavy_all_motion` | 保留全分族 motion，同時更強保護靜態邊界 | 三者中最好；但只是小幅平衡，不是突破 |

R44C 與 R42 / R44B 對照表如下，數字越低越好：

| 模型 | 整體位移誤差 px | 整體邊界距離 px | 格線位移誤差 px | 細線邊界距離 px | 大區塊邊界距離 px | 混合場景邊界距離 px | 缺陷邊界距離 px |
|---|---:|---:|---:|---:|---:|---:|---:|
| R42 best | 0.4609 | **3.6726** | 2.7911 | 2.4190 | **7.3401** | **6.6915** | 5.3471 |
| R44B from R42 | **0.3813** | 3.7276 | **2.2457** | 2.3368 | 7.5878 | 6.9202 | 5.3682 |
| R44C low motion static guard | 0.4115 | 3.7399 | 2.4615 | 2.3649 | 7.6882 | 6.8302 | 5.3514 |
| R44C family holdout motion | 0.4904 | 3.7342 | 3.0117 | 2.3301 | 7.7216 | 6.8645 | 5.3442 |
| R44C static heavy all motion | 0.4011 | 3.7198 | 2.3820 | **2.3291** | 7.7098 | 6.7994 | **5.3469** |

R44C 判讀：

- `r44c_static_heavy_all_motion` 是 R44C 最佳探針，但它不是全面勝出。它比 R44B 稍微改善整體邊界、細線、混合場景與缺陷，但整體位移與格線位移都比 R44B 退回。
- `family_holdout` 是最重要的否定結果：把大區塊與混合場景排除出 motion 並沒有保住它們，表示問題不是「這兩類不要學位移」這麼簡單。
- 大區塊仍是最明顯瓶頸。R44C 最佳探針的大區塊邊界距離 `7.7098 px`，比 R44B 的 `7.5878 px` 與 R42 的 `7.3401 px` 都差。
- 下一輪不能只調權重。需要讓不同顯微結構有不同的邊界/位移目標，尤其要單獨處理大面積邊界與混合場景。

R44C 最佳探針本地環形代理紀錄：

| 尺度 | R44C internal step std y | COMBO internal step std y | 相對 COMBO |
|---|---:|---:|---:|
| 8px | 0.1897 | 0.1389 | +36.6% |
| 0.8px | 0.2222 | 0.1509 | +47.2% |
| 0.08px | 0.1585 | 0.1185 | +33.8% |

判讀：R44C 在 8px 舊代理上比 R44B 稍微好一些，但 0.8px / 0.08px 沒有改善；仍只列為研究紀錄，不送外部 GMF。

## R44D 分族診斷

R44D 不開新 round、不訓練新模型。它只讀取 R44A/R44B/R44C 已有的逐 pair 位移結果，拆成「結構類型 × 位移段 × 模型」來看。

R44D 的目的，是避免因為 R44C 只小幅改善就馬上開新一輪；先判斷問題到底是全域權重不對，還是不同顯微結構真的需要不同處理。

最重要結論：

- 最佳單一模型平均邊界距離仍是 `R42 best`：`3.6726 px`。
- 若每個結構類型都拿目前最好的模型，分族上限是 `3.2038 px`，比最佳單一模型還有 `12.77%` 空間。
- 大區塊最佳邊界模型是 `R41 direct`，不是 R42/R44B/R44C。
- 混合場景最佳邊界模型是 `R44B from R40`。
- 格線的模型輸出位移最佳是 `R44B from R42`，但現有 `grid_phase_motion_error_px` 欄位對所有模型幾乎相同，不能用來排名模型；之後格線應看輸出影像的位移誤差與邊界距離。

分族最佳邊界結果：

| 結構類型 | 邊界最佳模型 | 邊界距離 px |
|---|---|---:|
| 曲線 | R44C static heavy | 1.8398 |
| 缺陷 | R44C family holdout | 5.3442 |
| 格線 | R42 best | 0.3806 |
| 交叉線 | R44C family holdout | 1.6259 |
| 大區塊 | R41 direct | 4.9915 |
| 混合場景 | R44B from R40 | 5.9151 |
| 細線 | R44C static heavy | 2.3291 |

分族診斷判讀：

- R44B/R44C 沒有失去所有能力；它們在細線、曲線、格線、交叉線上已接近 R42 或略有改善。
- 真正拖住整體的是大區塊與混合場景。這兩類的最佳來源不同，代表下一步不能只把一個 loss 權重加大或減小。
- R44C 的 `family_holdout` 失敗後，R44D 進一步確認：大區塊與混合場景不是「不要學位移」就能救回來，而是需要自己的邊界保護方式。

R44D 產物：

- R44D 主診斷報告：`reports/R44D_FAMILY_DIAGNOSTIC.md`
- 分族總表：`results/diagnostics/r44d_family_scorecard.csv`
- 位移段總表：`results/diagnostics/r44d_shift_scorecard.csv`
- 每族最佳模型表：`results/diagnostics/r44d_best_by_family.csv`
- 指標有效性檢查：`results/diagnostics/r44d_metric_discrimination.csv`
- 邊界熱圖：`results/diagnostics/r44d_boundary_heatmap.png`
- 位移熱圖：`results/diagnostics/r44d_motion_heatmap.png`

R44D 結論：當時不建議立刻開 R45，而是先留在 R44 內部做 R44E 小探針。R44E 已完成，結果見下一節。

## R44E 大區塊與混合場景專項探針

R44E 是 R44 內部追加探針，不是新 round。目的很窄：只測試「從不同既有起點出發，針對大區塊與混合場景做短訓練修補」是否足夠。

三個探針皆完成 14 epoch、每 epoch 60 train batches。因為 14 epoch 低於主訓練器的 best 更新門檻，本段評估使用每次訓練的 `latest.pth.tar`，不是 `best_tradeoff.pth.tar`。

| 探針 | 起點 | 判讀 |
|---|---|---|
| `r44e_region_mix_repair_from_r44b_r42` | R44B from R42 | 保住整體位移，混合場景小幅改善，但大區塊更差，不是突破 |
| `r44e_region_prior_from_r41` | R41 direct | 大區塊只小幅接近 R42，但格線與整體位移大幅退步 |
| `r44e_mixed_prior_from_r44b_r40` | R44B from R40 | 大區塊/混合場景小幅接近 R42，但格線與整體位移大幅退步 |

R44E 與 R42/R44B/R44C 對照如下，數字越低越好：

| 模型 | 整體位移誤差 px | 整體邊界距離 px | 格線位移誤差 px | 大區塊邊界距離 px | 混合場景邊界距離 px |
|---|---:|---:|---:|---:|---:|
| R42 best | 0.4609 | 3.6726 | 2.7911 | 7.3401 | 6.6915 |
| R44B from R42 | 0.3813 | 3.7276 | 2.2457 | 7.5878 | 6.9202 |
| R44B from COMBO | 0.5313 | 3.9081 | 3.2741 | 5.9436 | 6.9901 |
| R44B from R40 | 0.9087 | 3.7808 | 5.9051 | 6.9774 | 5.9151 |
| R44C static heavy | 0.4011 | 3.7198 | 2.3820 | 7.7098 | 6.7994 |
| R44E repair from R44B/R42 | 0.3820 | 3.7421 | 2.2420 | 7.7581 | 6.6060 |
| R44E region prior from R41 | 1.3705 | 5.9104 | 9.1453 | 7.2545 | 7.1743 |
| R44E mixed prior from R44B/R40 | 1.0646 | 4.1191 | 6.9561 | 7.2954 | 6.6220 |

R44E 判讀：

- 最接近可用的是 `R44E repair from R44B/R42`，但它只把混合場景從 R44B 的 `6.9202 px` 拉到 `6.6060 px`，同時大區塊從 `7.5878 px` 退到 `7.7581 px`；整體邊界也沒有贏過 R42。
- 從 R41 或 R44B/R40 出發，確實能稍微碰到目標分族，但格線位移會退到 `9.1453 px` 或 `6.9561 px`，代表這不是可接受的整體修補。
- R44E 沒有找到新的堪用候選，也不建議送外部 GMF。
- 這是一個有價值的否定結果：問題不是「對大區塊/混合場景多訓練一點」就能解，而是需要更明確的分族目標、分族選擇機制，或重新檢查大區塊邊界標註/量測定義。

R44E 產物：

- R44E 專項報告：`reports/R44E_TARGETED_PROBE.md`
- R44E 啟動器：`scripts/launch_r44e_probe.py`
- R44E 總表：`results/summary/r44e_probe_summary.csv`
- R44E 代表圖：`results/visual_samples/r44e_region_mixed_probe_sheet.png`

## R44F 大區塊與混合場景錯誤解剖

R44F 是 R44 內部診斷，不訓練、不開新模型。它針對 R44E 後留下的核心問題：大區塊與混合場景到底是真的重建不好，還是評估指標把合理結果判壞。

R44F 做了三件事：

- 從既有逐 pair 結果自動挑出 16 個錯誤案例。
- 用答案邊界人工製造 1px、2px、5px 偏移，以及邊界變厚/變薄/缺角，檢查指標是否可靠。
- 產出錯誤解剖代表圖；綠色是答案邊界，紅色是模型輸出邊界，黃色是重疊區。

指標壓力測試摘要如下：

| 類型 | 1px 偏移 | 5px 偏移 | 邊界變厚 |
|---|---:|---:|---:|
| large_regions | 0.5335 | 2.5477 | 1.5596 |
| mixed_fields | 0.5673 | 2.6217 | 1.5794 |

R44F 判讀：

- 目前沒有證據顯示只是指標誤判。人工偏移會讓指標明確變差，代表邊界距離指標有基本辨識力。
- 但指標也會懲罰邊界變厚、碎裂、缺角；這是合理的忠實度要求，也說明下一輪不能只追清晰或高頻。
- 大區塊與混合場景常出現「位移向量已經很準，但邊界距離仍很高」的情況。這代表問題不是整張圖沒跟著移動，而是邊界形狀、厚度、角點、直邊與小細節不夠忠實。
- R44E 失敗的原因更清楚了：短訓練只在既有能力間拉扯，沒有改變邊界形狀產生方式。

R44F 產物：

- R44F 診斷報告：`reports/R44F_ERROR_DIAGNOSTIC.md`
- R44F 診斷腳本：`scripts/r44f_error_diagnostics.py`
- R44F selected cases：`results/diagnostics/r44f_selected_cases.csv`
- R44F metric stress：`results/diagnostics/r44f_metric_stress.csv`
- R44F 代表圖：`results/visual_samples/r44f_error_dissection_sheet.png`

## R44G 邊界形狀體檢

R44G 是 R44 內部診斷，不訓練、不新增模型。它延續 R44F 的結論，把大區塊與混合場景的肉眼問題拆成四個分項：

- 邊界厚度是否接近答案。
- 邊界是否破碎成太多片段。
- 直線邊是否保留。
- 角點是否保留。

這次實際讀取 `12` 個模型資料夾、共 `11,760` 張 R44 位移重建影像，輸出逐張影像表、分族分數表與熱圖。

大區塊與混合場景合併排名如下，分數越低越好：

| 模型 | 形狀錯誤 | 邊界 F | 厚度比 | 破碎比 | 直邊保留 | 角點保留 |
|---|---:|---:|---:|---:|---:|---:|
| R44B from R40 | **0.3110** | 0.8114 | 1.0011 | 4.3366 | 0.8023 | 0.7413 |
| R41 direct | 0.3119 | **0.8304** | 1.0004 | 4.1915 | **0.8313** | 0.7371 |
| R44E mixed prior from R44B/R40 | 0.3284 | 0.8002 | 1.0013 | 4.7702 | 0.7868 | 0.7283 |
| R44B from COMBO | 0.3288 | 0.8073 | 1.0008 | **3.5495** | 0.7947 | 0.7010 |
| R42 best | 0.3298 | 0.8062 | 1.0009 | 5.2584 | 0.7942 | **0.7533** |
| R44B from R42 | 0.3384 | 0.8027 | 1.0012 | 5.9485 | 0.7901 | 0.7436 |
| COMBO | 0.4032 | 0.7003 | 1.0019 | 2.9171 | 0.6608 | 0.3946 |

分族看會更清楚：

- 大區塊形狀最好的是 `R44B from COMBO`，形狀錯誤 `0.3755`；這和 R44D/R44E 的大區塊邊界距離結果相互呼應。
- 混合場景形狀最好的是 `R44C static heavy`，形狀錯誤 `0.2181`；`R42 best`、`R44E repair`、`R44B from R42` 緊跟在後。
- `R44B from R42` 仍是最佳通用位移候選，但它在大區塊/混合場景形狀上不是最強。
- `R44B from R40` 與 `R41 direct` 在大區塊/混合場景形狀上更接近可用底子，但前面 R44D/R44E 已顯示它們會拉壞格線或整體位移。

R44G 判讀：

- R44F 的肉眼判斷成立：問題不是只有位移或單一邊界距離，而是邊界形狀本身不夠穩。
- 目前不是「完全沒有堪用能力」；不同模型各自保留了不同結構的能力。
- 也不是「挑一個現成模型就能解」；最佳位移、最佳大區塊形狀、最佳混合場景形狀分散在不同候選上。
- 下一步若繼續訓練，應該把大區塊、混合場景、格線分開處理，並直接約束厚度、破碎、直邊與角點；單純再做短訓練或全域權重調整不值得。

R44G 產物：

- R44G 診斷報告：`reports/R44G_BOUNDARY_SHAPE_METRICS.md`
- R44G 診斷腳本：`scripts/r44g_boundary_shape_metrics.py`
- R44G 逐張影像表：`results/diagnostics/r44g_boundary_shape_rows.csv`
- R44G 分族分數表：`results/diagnostics/r44g_boundary_shape_scorecard.csv`
- R44G 大區塊/混合場景排名：`results/diagnostics/r44g_boundary_shape_target_rank.csv`
- R44G JSON：`results/diagnostics/r44g_boundary_shape_scorecard.json`
- R44G 熱圖：`results/visual_samples/r44g_boundary_shape_heatmap.png`

## R44H Step 0 / Step A 家族平均探測

R44H 目前只完成 Step 0 與 Step A，不訓練新模型。這一步的目的很窄：先檢查 `R44C static heavy` 能不能作為之後混合場景的局部老師，再只在 R44B 三兄弟內做權重平均，確認「把已分散能力用簡單平均拼回來」是否可行。

Step 0 結論：

- `R44C static heavy` 可暫列為乾淨的混合場景局部老師。
- 混合場景形狀錯誤從 `R44B from R42` 的 `0.2230` 降到 `0.2181`。
- 大區塊/混合相關位移最大退步 `6.07%`，低於本次暫設的 `10%` 檢查線。

Step A 四個平均候選全部完成 R44 位移重建、邊界形狀分族評估與本地三尺度環形代理紀錄。結果如下：

| 候選 | 大區塊+混合形狀錯誤↓ | 整體位移誤差 px↓ | 本地環形 8px | 本地環形 0.8px | 本地環形 0.08px | 判定 |
|---|---:|---:|---:|---:|---:|---|
| `r44h_b42_bcombo_a050` | **0.2955** | 0.5298 | 0.2385 | 0.1902 | 0.1768 | 形狀最佳，但位移退步過大 |
| `r44h_b42_bcombo_a030` | 0.3036 | 0.5115 | 0.1882 | 0.1865 | 0.1695 | 形狀改善，但位移退步過大 |
| `r44h_b42_b40_bcombo_050_025_025` | 0.3093 | 0.6277 | 0.2295 | 0.1907 | 0.1878 | 形狀接近 R44B from R40，但位移退步過大 |
| `r44h_b42_b40_a030` | 0.3262 | 0.4843 | 0.1904 | 0.2168 | 0.1593 | 弱形狀改善，但位移退步過大 |

R44H Step A 判讀：

- 權重平均確實能把大區塊/混合場景形狀往好方向推，最佳形狀錯誤 `0.2955` 甚至優於 R44G 既有最低 `R44B from R40` 的 `0.3110`。
- 但代價很明顯：最佳通用位移候選 `R44B from R42` 的整體位移誤差是 `0.3813 px`，四個平均候選都退到 `0.4843-0.6277 px`。
- 本地環形代理也沒有自然救回來；8px 與 0.8px 多數仍比 COMBO/R44B from R42 差。
- 因此 Step A 沒有找到適合作為下一步起點的平均候選。平均可以證明能力能被拉動，但不能作為「匯聚到單一模型」的主要解法。

R44H Step A 下一步：

- 不建議用四個 R44H 平均候選進一步訓練。
- 下一個合理動作是回到 `R44B from R42` 當學生起點，做單一老師、局部遮罩式蒸餾概念驗證；先只讓 `R44B from COMBO` 教大區塊邊界，不把多老師一次全放進去。
- 若單一老師都不能在不毀掉位移的前提下改善大區塊，後續多老師蒸餾就不應擴張，應轉向 adapter / 分族小頭或推論時分族選擇。

R44H Step A 產物：

- R44H 主報告：`reports/R44H_STEPA_FAMILY_AVERAGE.md`
- R44H 平均工具：`scripts/r44h_family_average.py`
- R44H 測試：`tests/test_r44h_family_average.py`
- R44H Step A 總表：`results/r44h_family_average/r44h_stepa_summary.csv`
- R44H Step A JSON：`results/r44h_family_average/r44h_stepa_summary.json`
- R44H 平均候選權重：`results/r44h_family_average/checkpoints/`
- R44H 位移分族表：`results/diagnostics/r44h_family_scorecard.csv`
- R44H 邊界形狀分族表：`results/diagnostics/r44h_boundary_shape_scorecard.csv`
- R44H 大區塊/混合場景排名：`results/diagnostics/r44h_boundary_shape_target_rank.csv`
- R44H 本地環形代理紀錄：`results/ring_guard/r44h_*_ring_guard_summary.json`

## R44H Step B 局部老師蒸餾概念驗證

R44H Step B 已完成正式短訓練與完整本地測試。這一步的目標是檢查：從最佳通用位移候選 `R44B from R42` 出發，只在大區塊邊界帶向 `R44B from COMBO` 學習，能不能在不破壞位移的前提下修復大區塊形狀。

結果：**沒有通過概念驗證**。

| 指標 | R44B from R42 | R44H Step B | 判讀 |
|---|---:|---:|---|
| 整體位移誤差↓ | `0.3813 px` | `0.3837 px` | 幾乎守住 |
| 格線位移誤差↓ | `2.2457 px` | `2.2393 px` | 持平略好 |
| 邊界位移距離↓ | `3.7276 px` | `3.6648 px` | 小幅改善 |
| 大區塊+混合形狀錯誤↓ | `0.3384` | `0.3481` | 變差 |
| 大區塊形狀錯誤↓ | `0.4538` | `0.4667` | 變差 |
| 混合場景形狀錯誤↓ | `0.2230` | `0.2294` | 變差 |

本地環形代理只作紀錄：8px `0.2016`（+45.1% vs COMBO local）、0.8px `0.2146`（+42.2%）、0.08px `0.1623`（+37.0%）。

Step B 判讀：

- 局部老師蒸餾保住了 R44B from R42 的位移能力。
- 但它沒有把大區塊邊界往 R44B from COMBO 的方向拉，形狀與碎裂反而略差。
- 因此不建議進入原本的 R44H Step C 多老師蒸餾；單一老師在單一區域都不能改善，多老師版本更可能放大干擾。
- 下一步應改成 adapter / 分族小頭 / 推論時分族選擇等「能力分流後再整合」路線，而不是繼續做全模型微調。

R44H Step B 產物：

- Step B 報告：`reports/R44H_STEPB_REGION_KD.md`
- Step B 計畫：`reports/R44H_STEPB_REGION_KD_PLAN.md`
- Step B 文件追溯稽核：`reports/R44_HISTORY_TRACEABILITY_AUDIT.md`
- Step B 啟動腳本：`scripts/launch_r44h_stepb.py`
- Step B 測試：`tests/test_r44h_region_kd.py`、`tests/test_r44h_stepb_launcher.py`
- Step B 評估 checkpoint：`results/r44h_stepb_region_kd/checkpoints/r44h_stepb_region_kd_main_latest.pth.tar`
- Step B 位移摘要：`results/r44h_stepb_region_kd/r44h_stepb_motion_summary.json`
- Step B 環形代理摘要：`results/r44h_stepb_region_kd/r44h_stepb_ring_guard_summary.json`

## 代表圖

- R42 起點 vs R44B 主候選拼圖：`results/visual_samples/r44_motion_r42_vs_r44_contact_sheet.png`
- R42 / R44B / R44C 探針拼圖：`results/visual_samples/r44c_probe_r42_r44b_r44c_sheet.png`
- R44D 邊界分族熱圖：`results/diagnostics/r44d_boundary_heatmap.png`
- R44D 位移分族熱圖：`results/diagnostics/r44d_motion_heatmap.png`
- R44E 大區塊/混合場景拼圖：`results/visual_samples/r44e_region_mixed_probe_sheet.png`
- R44F 錯誤解剖拼圖：`results/visual_samples/r44f_error_dissection_sheet.png`
- R44G 邊界形狀熱圖：`results/visual_samples/r44g_boundary_shape_heatmap.png`
- R44A/R44B 總表：`results/summary/r44_motion_summary_all.csv`
- R44A/R44B 總表 JSON：`results/summary/r44_motion_summary_all.json`
- R44C 探針總表：`results/summary/r44c_probe_summary.csv`
- R44C 探針總表 JSON：`results/summary/r44c_probe_summary.json`
- R44E 探針總表：`results/summary/r44e_probe_summary.csv`
- R44E 探針總表 JSON：`results/summary/r44e_probe_summary.json`
- R44F selected cases：`results/diagnostics/r44f_selected_cases.csv`
- R44F metric stress：`results/diagnostics/r44f_metric_stress.csv`
- R44G 邊界形狀分數表：`results/diagnostics/r44g_boundary_shape_scorecard.csv`
- R44H Step A 總表：`results/r44h_family_average/r44h_stepa_summary.csv`
- R44H Step B 位移摘要：`results/r44h_stepb_region_kd/r44h_stepb_motion_summary.json`
- R44H Step B 環形代理摘要：`results/r44h_stepb_region_kd/r44h_stepb_ring_guard_summary.json`

代表圖肉眼判讀：

- R42 與 R44B 主候選都已能清楚重建細線、格線、曲線與缺陷。
- R44B 主候選在位移指標上比 R42 更忠實，但大區塊與混合場景肉眼差異不大，且指標顯示略退。
- R44C 最佳探針不是肉眼可見的大突破；它較像是把 R44B 的過度位移修正稍微拉回，但沒有真正解開大區塊與混合場景問題。
- R44D 熱圖顯示 R42/R44B/R44C 在細線、曲線、格線、交叉線上已經靠近好區間，但大區塊與混合場景仍明顯偏弱。
- R44E 代表圖顯示大區塊與混合場景只有很小差異，沒有出現足以支持長訓練或升級的肉眼突破。
- R44F 代表圖與壓力測試顯示，大區塊/混合場景的問題不是整體位移沒有跟上，而是邊界形狀、厚度、碎裂、角點與直邊保持不夠穩。
- R44G 熱圖顯示同一個結論的分數版：大區塊、混合場景、格線的最佳來源分散在不同模型，沒有單一現成候選全面勝出。
- R44H Step A 顯示簡單權重平均可以讓大區塊/混合場景形狀變好，但會把整體位移拉壞；這支持下一步要做局部蒸餾，而不是繼續做全域平均。
- R44H Step B 顯示局部老師蒸餾可以保住位移，但不能修復大區塊/混合場景形狀；這代表多老師全模型蒸餾不應直接擴張。
- 目前真正瓶頸不是「能不能重建清楚」，而是「位移訓練不能只改善格線與整體位移，還要保住大區塊/混合場景邊界」。

## 結論

R44 第一版是**研究成功但不可升級**。

成功之處：

- 把問題從單張清晰度推進到已知位移下的通用邊界忠實度。
- 找到 R42 作為最佳起點。
- `R44B from R42` 把整體位移誤差與格線位移誤差再往下推。
- R44C 進一步證明，問題不是單純調低 motion 強度或排除部分結構就能解決。
- R44D 證明目前還不需要快速開新 round。
- R44E 證明只針對大區塊與混合場景做短訓練修補，也不足以產生新堪用候選。
- R44F 證明目前不能把大區塊/混合場景失敗簡化成指標誤判；更像是真正的邊界形狀忠實度問題。
- R44G 進一步量化這個問題，並指出最佳位移、最佳大區塊形狀、最佳混合場景形狀分散在不同模型。
- R44H Step A 證明 R44B 家族權重平均可以改善目標形狀分數，但無法在位移不明顯退步的前提下匯聚能力。
- R44H Step B 證明單一老師局部蒸餾沒有成功匯聚能力；位移守住了，但目標形狀錯誤變差。

不足之處：

- 大區塊與混合場景邊界未同步改善。
- 本地環形舊代理測試退步明顯。
- R44C 沒有找到可直接接近「堪用平衡」的候選。
- R44E 也沒有找到可直接接近「堪用平衡」的候選。
- R44F 顯示還缺少直接衡量邊界厚度、碎裂、角點/直邊保持的分項指標。
- R44G 補上分項指標後，確認現成候選仍沒有全面平衡；R44B from R40 / R41 有形狀底子，但會犧牲整體位移或格線。
- R44H Step A 的四個平均候選都因整體位移退步過大，不建議作為後續訓練起點。
- R44H Step B 也未找到可用修補方向，不建議繼續做 Step C 多老師蒸餾。
- 現有格線 phase 欄位不是有效模型比較指標，需要在後續修正或改用輸出影像導出的格線相位檢查。
- 尚未送外部 GMF；即使送測，也只應作研究紀錄，不應作升級前提。

下一步建議：

- 不要直接把 R44B 主候選升級。
- 下一輪應針對「motion 讓格線與整體位移變好，但沒有保住大區塊/混合場景邊界」設計真正分族的目標，而不是只做全域權重調整。
- 大區塊、混合場景與格線需要分開處理；目前單一 motion 目標會讓不同結構互相拉扯。
- 短期不建議繼續做全模型微調小修；R44G 已補上邊界厚度、碎裂、角點/直邊保持指標，下一步應用這些指標設計真正分族的訓練/選擇機制。
- 若繼續新一輪，優先考慮 adapter / 分族小頭 / 推論時分族選擇，把分散在不同模型的能力以較低干擾方式整合。
- 若仍要顧及舊環形代理能力，應在下一輪把環形當作額外紀錄/正則，而不是重新把它設為主要目標。
