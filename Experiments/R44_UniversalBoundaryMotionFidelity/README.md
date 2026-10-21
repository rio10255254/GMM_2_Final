# R44 — 通用顯微邊界位移忠實度

## 假說

R42 已證明模型可以把未看過的顯微邊界重建得更清楚，但也暴露出另一個問題：單張圖清楚，不代表同一個結構在連續位移下會穩定地跟著真實位置移動。

R44 的假說是：如果直接建立「已知位移」的通用顯微結構序列，並用邊界、中心線、格線相位與小缺陷位置來量測，模型可以從單張邊界清晰度進一步走向位移忠實度。

## 設計

R44 分成兩段：

| 階段 | 內容 | 狀態 |
|---|---|---|
| R44A | 先跑診斷：COMBO、R39、R40、R41、R42 候選在已知位移顯微結構上誰真的穩 | 已完成 |
| R44B | 再訓練：把 R42 靜態邊界資料與 R44 位移序列一起用，修正通用邊界漂移 | 三個候選皆已完成 24 epoch |
| R44C | 追加短探針：測試降低 motion、排除部分結構、加強靜態邊界是否能取得平衡 | 三個探針皆已完成 21 epoch |
| R44D | 不訓練，只拆解既有結果：按結構類型、位移段、模型來源找出真正瓶頸 | 已完成 |
| R44E | 追加小探針：只針對大區塊與混合場景做短訓練修補 | 三個探針皆已完成 14 epoch；沒有找到新堪用候選 |
| R44F | 不訓練，只做錯誤解剖：檢查大區塊/混合場景是模型問題還是指標問題 | 已完成；確認不是單純指標誤判 |
| R44G | 不訓練，只做邊界形狀體檢：量化厚度、破碎、直邊與角點保留 | 已完成；確認現成候選能力分散，不能只挑單一模型解決 |
| R44H Step A | 不訓練，只做 R44B 家族平均與 R44C 乾淨度檢查 | 已完成；形狀可改善，但整體位移退步過大 |

R44 第一版不改模型本體，不加入真實影像。環形仍保留為舊能力紀錄，但你已決定 R44 研究不設環形淘汰線；外部 GMF 只記錄，不否定本輪研究價值。

## 資料

R44 新增七類位移序列：

| 資料階段 | 類型 | 檢查重點 |
|---|---|---|
| `stage_41_motion_lines` | 細線 | 線條是否跟著位移，不斷裂、不跳動 |
| `stage_42_motion_grids` | 格線 | pitch / phase 是否跟著已知位移 |
| `stage_43_motion_junctions` | 交叉線 | 交會處是否漂移 |
| `stage_44_motion_curves` | 曲線 | 曲線邊界是否穩定移動 |
| `stage_45_motion_regions` | 大區塊 | 大面積邊界是否跟錯、變圓或波紋化 |
| `stage_46_motion_defects` | 缺陷 | 小缺陷位置與面積是否漂移 |
| `stage_47_motion_mixed` | 混合場景 | 大形狀與小細節是否同時保持位移忠實 |

每組序列包含 `0 / 0.08 / 0.16 / 0.4 / 0.8 / 2 / 8 px` 的已知位移，並為每一幀產生來源圖、答案圖、邊界遮罩、中心線遮罩、距離圖與 metadata。

## 候選

| 候選 | 起點 | 用途 |
|---|---|---|
| `r44_motion_from_r42_best` | R42 `r42_r41_best` | 主候選：保留 R42 邊界能力，修正通用位移忠實度 |
| `r44_motion_from_r40_a045` | R40 a045 | 檢查較溫和顯微能力起點是否更穩 |
| `r44_motion_from_combo` | COMBO | 保守基準：確認從正式 baseline 能否學到位移忠實度 |

## 評估

- R44 位移測試：邊界位移誤差、中心線位移誤差、格線相位位移誤差、小缺陷漂移。
- R42 靜態邊界測試：確認位移訓練沒有把單張邊界能力洗掉。
- R40 顯微特徵測試與 R39 多圖形測試：確認能力沒有只偏向單一類資料。
- 本地三尺度環形與外部 GMF：只作舊能力紀錄，不作 R44 研究淘汰線。

## 目前結果

目前狀態是：**R44A 診斷完成，R44B 三個候選完成訓練與位移測試，R44C 三個短探針、R44D 分族診斷、R44E 專項探針、R44F 錯誤解剖、R44G 邊界形狀體檢與 R44H Step A 家族平均探測皆已完成；研究成功但不可升級，也沒有單一現成堪用候選。**

已完成：

- R44 位移資料產生器。
- R44 位移指標。
- R44 訓練啟動器。
- R44 位移重建、環形紀錄、外部 GMF 紀錄腳本。
- 主訓練器新增可關閉的通用 motion dataset / motion loss 接口。
- R44 單元測試與 trainer 接線測試。
- R44A COMBO/R39/R40/R41/R42 全基準診斷。
- R44B `r44_motion_from_r42_best`、`r44_motion_from_r40_a045`、`r44_motion_from_combo` 三候選訓練。
- R44B 位移測試、總表、代表圖與主候選本地三尺度環形代理紀錄。
- R44C `r44c_low_motion_static_guard`、`r44c_family_holdout_motion`、`r44c_static_heavy_all_motion` 三個短探針訓練。
- R44C 位移測試、總表、代表圖與最佳探針本地三尺度環形代理紀錄。
- R44D 分族診斷、位移段分析、指標有效性檢查與熱圖。
- R44E 大區塊/混合場景三個短探針、位移測試、總表與代表圖。
- R44F 大區塊/混合場景錯誤解剖、指標壓力測試、案例表與代表圖。
- R44G 邊界厚度、破碎、直邊與角點保留體檢、分族分數表與熱圖。
- R44H Step 0 / Step A：R44C 乾淨度檢查、四個 R44B 家族平均候選、位移測試、邊界形狀分族測試與本地環形代理紀錄。

重點結論：

- `r44_motion_from_r42_best` 是目前最佳通用位移候選，整體位移誤差 `0.3813 px`，格線位移誤差 `2.2457 px`。
- 它讓 R42 的位移忠實度再進一步，但大區塊與混合場景邊界沒有同步改善。
- R44C 最佳探針 `r44c_static_heavy_all_motion` 只取得小幅平衡；單純降低 motion 或排除大區塊/混合場景都沒有真正解決問題。
- R44D 顯示最佳單一模型仍是 R42 best；若每個結構類型都拿目前最佳模型，邊界平均還有約 `12.77%` 空間，表示下一步要分族處理，不應急著開 R45。
- R44D 也確認目前 `grid_phase_motion_error_px` 不能分辨模型，後續格線應看輸出影像的位移誤差與邊界距離。
- R44E 確認只對大區塊/混合場景做短訓練修補不夠；最接近可用的 `r44e_region_mix_repair_from_r44b_r42` 保住整體位移，但大區塊更差，另外兩個探針會把格線與整體位移拉壞。
- R44F 確認大區塊/混合場景不是單純指標誤判；人工偏移能被指標抓到，但模型常在位移準確時仍出現邊界變厚、碎裂、直邊/角點不穩。
- R44G 確認現成模型的能力是分散的：`R44B from R40` 和 `R41 direct` 在大區塊/混合場景形狀較好，`R44B from R42` 仍是位移最好，但沒有單一候選同時吃下所有結構。
- R44H Step A 確認 R44B 家族平均能把大區塊/混合形狀錯誤推到 `0.2955`，但整體位移會退到 `0.5298 px` 以上，所以不適合作為後續起點。
- 本地三尺度環形代理退步明顯，因此不可當作量測替代候選。

## 主要資料與產物

| 類型 | 位置 |
|---|---|
| 資料產生器 | `scripts/r44_motion_data.py` |
| 位移指標 | `scripts/r44_motion_metrics.py` |
| 訓練啟動器 | `scripts/launch_r44.py` |
| R44C 探針啟動器 | `scripts/launch_r44c_probe.py` |
| R44E 探針啟動器 | `scripts/launch_r44e_probe.py` |
| R44F 錯誤解剖 | `scripts/r44f_error_diagnostics.py` |
| R44G 邊界形狀體檢 | `scripts/r44g_boundary_shape_metrics.py` |
| R44H 家族平均工具 | `scripts/r44h_family_average.py` |
| R44D 診斷工具 | `scripts/r44d_family_diagnostics.py` |
| 位移重建 | `scripts/run_r44_motion_recon.py` |
| 本地環形紀錄 | `scripts/run_r44_ring_guard.py` |
| 外部 GMF 紀錄 | `scripts/r44_external_compare.py` |
| 結果報告 | `reports/R44_RESULTS.md` |
| R44C 探針計畫 | `reports/R44C_PROBE_PLAN.md` |
| R44D 診斷報告 | `reports/R44D_FAMILY_DIAGNOSTIC.md` |
| R44E 專項報告 | `reports/R44E_TARGETED_PROBE.md` |
| R44F 診斷報告 | `reports/R44F_ERROR_DIAGNOSTIC.md` |
| R44G 形狀體檢報告 | `reports/R44G_BOUNDARY_SHAPE_METRICS.md` |
| R44H Step A 報告 | `reports/R44H_STEPA_FAMILY_AVERAGE.md` |
| R44A/R44B 總表 | `results/summary/r44_motion_summary_all.csv` |
| R44C 探針總表 | `results/summary/r44c_probe_summary.csv` |
| R44E 探針總表 | `results/summary/r44e_probe_summary.csv` |
| R44F selected cases | `results/diagnostics/r44f_selected_cases.csv` |
| R44F metric stress | `results/diagnostics/r44f_metric_stress.csv` |
| R44G 邊界形狀分數表 | `results/diagnostics/r44g_boundary_shape_scorecard.csv` |
| R44G 大區塊/混合場景排名 | `results/diagnostics/r44g_boundary_shape_target_rank.csv` |
| R44H Step A 總表 | `results/r44h_family_average/r44h_stepa_summary.csv` |
| R44H 邊界形狀分數表 | `results/diagnostics/r44h_boundary_shape_scorecard.csv` |
| R44D 分族診斷 | `results/diagnostics/r44d_family_scorecard.csv` |
| 代表圖 | `results/visual_samples/r44_motion_r42_vs_r44_contact_sheet.png` |
| R44C 代表圖 | `results/visual_samples/r44c_probe_r42_r44b_r44c_sheet.png` |
| R44E 代表圖 | `results/visual_samples/r44e_region_mixed_probe_sheet.png` |
| R44F 代表圖 | `results/visual_samples/r44f_error_dissection_sheet.png` |
| R44G 邊界形狀熱圖 | `results/visual_samples/r44g_boundary_shape_heatmap.png` |
| R44D 邊界熱圖 | `results/diagnostics/r44d_boundary_heatmap.png` |
| 本地環形紀錄 | `results/ring_guard/r44_motion_from_r42_best_e24_ring_guard_summary.json` |
| R44C 本地環形紀錄 | `results/ring_guard/r44c_static_heavy_all_motion_ring_guard_summary.json` |

## 分支

`sandbox/r44`
