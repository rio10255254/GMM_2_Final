# R44 Manifest

## 實驗身份

- Round：R44
- 名稱：通用顯微邊界位移忠實度
- 目錄：`Experiments/R44_UniversalBoundaryMotionFidelity/`
- 分支：`sandbox/r44`
- 主要目標：讓顯微結構的邊界、中心線、格線相位與缺陷位置在已知位移下保持忠實，不只讓單張圖看起來清楚。

## 主要檔案

| 類型 | 位置 | 用途 |
|---|---|---|
| 資料產生 | `scripts/r44_motion_data.py` | 產生 R44 位移序列、幾何標註與資料包 |
| 位移評估 | `scripts/r44_motion_metrics.py` | 計算位移向量誤差、邊界漂移與格線 phase 漂移 |
| 訓練啟動 | `scripts/launch_r44.py` | 啟動三個 R44B 候選 |
| R44C 探針啟動 | `scripts/launch_r44c_probe.py` | 啟動 R44C 三個短訓練探針 |
| R44E 探針啟動 | `scripts/launch_r44e_probe.py` | 啟動 R44E 三個大區塊/混合場景短訓練探針 |
| R44D 診斷 | `scripts/r44d_family_diagnostics.py` | 讀取既有逐 pair 結果，產生分族、位移段與指標有效性分析 |
| R44F 錯誤解剖 | `scripts/r44f_error_diagnostics.py` | 讀取既有重建與逐 pair 結果，產生大區塊/混合場景錯誤案例、壓力測試與代表圖 |
| R44G 邊界形狀體檢 | `scripts/r44g_boundary_shape_metrics.py` | 讀取既有重建影像，量化邊界厚度、破碎、直邊與角點保留 |
| R44H 家族平均探測 | `scripts/r44h_family_average.py` | 建立 R44B 家族平均候選，整理 Step 0/Step A 結果與報告 |
| 位移重建 | `scripts/run_r44_motion_recon.py` | 跑 R44A/R44B 位移測試重建 |
| 環形紀錄 | `scripts/run_r44_ring_guard.py` | 跑本地三尺度環形紀錄 |
| 外部紀錄 | `scripts/r44_external_compare.py` | 彙整外部 GMF；R44 只記錄，不作研究淘汰 |
| 測試 | `tests/` | R44 資料、指標、訓練器 motion 接線測試 |
| 主報告 | `reports/R44_RESULTS.md` | R44 canonical 結果紀錄 |
| R44C 探針計畫 | `reports/R44C_PROBE_PLAN.md` | R44C 設計、完成標準與判定方式 |
| R44D 診斷報告 | `reports/R44D_FAMILY_DIAGNOSTIC.md` | R44D 分族診斷與下一步判斷 |
| R44E 專項報告 | `reports/R44E_TARGETED_PROBE.md` | R44E 大區塊/混合場景探針結果與否定結論 |
| R44F 診斷報告 | `reports/R44F_ERROR_DIAGNOSTIC.md` | R44F 大區塊/混合場景錯誤解剖與後續策略 |
| R44G 形狀體檢報告 | `reports/R44G_BOUNDARY_SHAPE_METRICS.md` | R44G 邊界形狀分項指標、排名與後續策略 |
| R44H Step A 報告 | `reports/R44H_STEPA_FAMILY_AVERAGE.md` | R44C 乾淨度檢查與 R44B 家族權重平均探測 |
| 外部報告 | `reports/R44_EXTERNAL_COMPARE.md` | 外部 GMF 紀錄，待外部結果放入後產生 |

## 目前狀態

- R44A 全候選診斷已完成。
- R44B 三個候選皆已完成 24 epoch 訓練與位移測試。
- 主候選 `r44_motion_from_r42_best` 是目前最好的通用位移忠實候選，整體位移誤差 `0.3813 px`，格線位移誤差 `2.2457 px`。
- 主候選本地三尺度環形代理紀錄退步明顯：8px `+45.1%`、0.8px `+46.7%`、0.08px `+32.3%` vs COMBO。
- R44C 三個短訓練探針已完成；最佳探針 `r44c_static_heavy_all_motion` 只帶來小幅平衡，未找到可升級或可直接堪用的候選。
- R44C 重要結論：單純降低 motion 強度或把大區塊/混合場景排除在 motion 之外都無效；下一輪需要真正分族的邊界/位移目標。
- R44D 分族診斷已完成；最佳單一模型仍是 R42 best，分族上限相對最佳單一模型還有 `12.77%` 空間，短期不建議開 R45。
- R44D 額外確認：目前 `grid_phase_motion_error_px` 對所有模型幾乎相同，不能作模型排名；後續格線應看輸出影像位移誤差與邊界距離。
- R44E 三個大區塊/混合場景短訓練探針已完成；沒有找到新堪用候選。最接近可用的 `r44e_region_mix_repair_from_r44b_r42` 保住整體位移但沒有救回大區塊，另外兩個探針會讓格線與整體位移大幅退步。
- R44F 錯誤解剖已完成；確認大區塊/混合場景不是單純指標誤判。人工偏移可被指標抓到，但模型常在位移已準時仍有邊界變厚、碎裂、直邊/角點不穩。
- R44G 邊界形狀體檢已完成；確認現成候選能力分散，`R44B from R42` 位移最好但形狀不是最強，`R44B from R40` / `R41 direct` 在大區塊與混合場景形狀較好但會犧牲整體位移或格線。
- R44H Step 0 / Step A 已完成；`R44C static heavy` 可暫作混合場景局部老師，但四個 R44B 家族平均候選雖改善大區塊/混合形狀，整體位移皆退步過大，不建議作後續起點。
- R44H Step B 已完成；單一老師局部蒸餾守住位移但未改善大區塊/混合形狀，概念驗證失敗，不建議進入多老師 Step C。
- R44 第一版結論：研究成功但不可升級；外部 GMF 尚未送測，若送測也只作研究紀錄。
- 主訓練器已新增預設關閉的 motion 設定；未開啟 R44 時不影響舊實驗。
- R44 單元測試與專案結構檢查已通過。

## 預計資料包

| 資料包 | 位置 | 說明 |
|---|---|---|
| R44 motion train | `Training_Data/r44_universal_boundary_motion/r44_motion_research_train/` | R44B 通用位移訓練資料 |
| R44 motion validation | `Training_Data/r44_universal_boundary_motion/motion_val_unseen/` | R44A/R44B 未看過位移測試 |
| R44 geometry source | `Training_Data/r44_motion_geometry/` | 位移序列的邊界、中心線、距離圖與 metadata |
| R42 static boundary train | `Training_Data/r42_microscopy_boundary_fidelity/r42_boundary_research_train/` | R44B 保留靜態邊界能力的主訓練資料 |

## 訓練候選

| 候選 | 起點 checkpoint | 執行結果 |
|---|---|---|
| `r44_motion_from_r42_best` | R42 `r42_r41_best` | 已完成；最佳通用位移候選 |
| `r44_motion_from_r40_a045` | R40 a045 | 已完成；混合場景邊界較好，但格線位移偏差 |
| `r44_motion_from_combo` | COMBO | 已完成；大區塊邊界較好，但整體不如 R42 起點 |

## R44C 探針候選

| 探針 | 起點 checkpoint | 執行結果 |
|---|---|---|
| `r44c_low_motion_static_guard` | R42 `r42_r41_best` | 已完成；位移退回一些，邊界沒有明顯改善 |
| `r44c_family_holdout_motion` | R42 `r42_r41_best` | 已完成；排除大區塊/混合場景 motion 無效 |
| `r44c_static_heavy_all_motion` | R42 `r42_r41_best` | 已完成；三者中最佳，但只是小幅平衡，不可升級 |

## R44E 探針候選

| 探針 | 起點 checkpoint | 執行結果 |
|---|---|---|
| `r44e_region_mix_repair_from_r44b_r42` | R44B from R42 | 已完成；整體位移接近 R44B，混合場景小幅改善，但大區塊更差 |
| `r44e_region_prior_from_r41` | R41 direct | 已完成；大區塊只小幅接近 R42，但格線與整體位移大幅退步 |
| `r44e_mixed_prior_from_r44b_r40` | R44B from R40 | 已完成；目標分族小幅改善，但格線與整體位移大幅退步 |

## R44H Step A 平均候選

| 候選 | 來源 | 執行結果 |
|---|---|---|
| `r44h_b42_bcombo_a050` | 50% R44B from R42 + 50% R44B from COMBO | 形狀錯誤最佳 `0.2955`，但整體位移退到 `0.5298 px` |
| `r44h_b42_b40_a030` | 70% R44B from R42 + 30% R44B from R40 | 形狀小幅改善，整體位移退到 `0.4843 px` |
| `r44h_b42_bcombo_a030` | 70% R44B from R42 + 30% R44B from COMBO | 形狀改善，整體位移退到 `0.5115 px` |
| `r44h_b42_b40_bcombo_050_025_025` | 50% R44B from R42 + 25% R44B from R40 + 25% R44B from COMBO | 形狀接近既有最佳，但整體位移退到 `0.6277 px` |

## R44H Step B 局部蒸餾候選

| 候選 | 起點 | 執行結果 |
|---|---|---|
| `r44h_stepb_region_kd_main` | R44B from R42，向 R44B from COMBO 做大區塊邊界帶局部蒸餾 | 已完成；整體位移 `0.3837 px` 幾乎守住，但目標形狀錯誤 `0.3481` 比 R44B from R42 的 `0.3384` 更差 |

## 主要產物

| 類型 | 位置 | 說明 |
|---|---|---|
| R44A/R44B 總表 | `results/summary/r44_motion_summary_all.csv` | 所有比較模型與 R44B 候選的位移指標 |
| R44A/R44B 總表 JSON | `results/summary/r44_motion_summary_all.json` | 同一份結果的機器可讀版本 |
| R44 代表圖 | `results/visual_samples/r44_motion_r42_vs_r44_contact_sheet.png` | R42 起點與 R44B 主候選的七類結構對照 |
| R44C 代表圖 | `results/visual_samples/r44c_probe_r42_r44b_r44c_sheet.png` | R42、R44B 與 R44C 最佳探針的七類結構對照 |
| 位移重建結果 | `results/motion_recon/` | COMBO/R39/R40/R41/R42 與 R44B 候選的重建影像與分項結果 |
| 本地環形紀錄 | `results/ring_guard/r44_motion_from_r42_best_e24_ring_guard_summary.json` | R44B 主候選的三尺度本地環形代理紀錄 |
| R44C 探針總表 | `results/summary/r44c_probe_summary.csv` | R42、R44B 與三個 R44C 探針的指標對照 |
| R44C 探針總表 JSON | `results/summary/r44c_probe_summary.json` | 同一份結果的機器可讀版本 |
| R44C 本地環形紀錄 | `results/ring_guard/r44c_static_heavy_all_motion_ring_guard_summary.json` | R44C 最佳探針的三尺度本地環形代理紀錄 |
| R44D 分族總表 | `results/diagnostics/r44d_family_scorecard.csv` | 所有模型按結構類型拆分的位移與邊界指標 |
| R44D 位移段總表 | `results/diagnostics/r44d_shift_scorecard.csv` | 大小位移段的分項結果 |
| R44D 每族最佳模型表 | `results/diagnostics/r44d_best_by_family.csv` | 每個結構類型在各指標上的最佳候選 |
| R44D 指標有效性表 | `results/diagnostics/r44d_metric_discrimination.csv` | 確認哪些指標能分辨模型、哪些不能 |
| R44D 邊界熱圖 | `results/diagnostics/r44d_boundary_heatmap.png` | 分族邊界距離視覺化 |
| R44D 位移熱圖 | `results/diagnostics/r44d_motion_heatmap.png` | 分族位移誤差視覺化 |
| R44E 探針總表 | `results/summary/r44e_probe_summary.csv` | R42、R44B、R44C 與三個 R44E 探針的對照 |
| R44E 探針總表 JSON | `results/summary/r44e_probe_summary.json` | 同一份結果的機器可讀版本 |
| R44E 最佳指標表 | `results/summary/r44e_best_by_metric.json` | 各分項指標目前最佳來源 |
| R44E 代表圖 | `results/visual_samples/r44e_region_mixed_probe_sheet.png` | 大區塊與混合場景的 R42/R44B/R44C/R44E 對照 |
| R44E repair checkpoint | `results/archive_retained_20260824/training_checkpoints/training_progress_GESR_v1_v5_ST0p8_SWP_r44e_region_mix_repair_from_r44b_r42_20260507_035322/latest.pth.tar` | R44E 探針；D 保留 latest |
| R44E region-prior checkpoint | `results/archive_retained_20260824/training_checkpoints/training_progress_GESR_v1_v5_ST0p8_SWP_r44e_region_prior_from_r41_20260507_035819/latest.pth.tar` | R44E 探針；D 保留 latest |
| R44E mixed-prior checkpoint | `results/archive_retained_20260824/training_checkpoints/training_progress_GESR_v1_v5_ST0p8_SWP_r44e_mixed_prior_from_r44b_r40_20260507_040148/latest.pth.tar` | R44E 探針；D 保留 latest |
| R44F selected cases | `results/diagnostics/r44f_selected_cases.csv` | 大區塊/混合場景錯誤案例表 |
| R44F selected cases JSON | `results/diagnostics/r44f_selected_cases.json` | 同一份結果的機器可讀版本 |
| R44F metric stress | `results/diagnostics/r44f_metric_stress.csv` | 人工偏移、邊界變厚/變薄/缺角壓力測試 |
| R44F metric stress JSON | `results/diagnostics/r44f_metric_stress.json` | 同一份結果的機器可讀版本 |
| R44F metric stress summary | `results/diagnostics/r44f_metric_stress_summary.csv` | 壓力測試彙整表 |
| R44F 代表圖 | `results/visual_samples/r44f_error_dissection_sheet.png` | 大區塊/混合場景錯誤解剖拼圖 |
| R44G 逐張形狀表 | `results/diagnostics/r44g_boundary_shape_rows.csv` | 11,760 張 R44 位移重建影像的邊界形狀分項指標 |
| R44G 分族分數表 | `results/diagnostics/r44g_boundary_shape_scorecard.csv` | 各模型、各顯微結構類型的形狀錯誤彙整 |
| R44G 目標分族排名 | `results/diagnostics/r44g_boundary_shape_target_rank.csv` | 大區塊與混合場景合併後的邊界形狀排名 |
| R44G 分數 JSON | `results/diagnostics/r44g_boundary_shape_scorecard.json` | 同一份結果的機器可讀版本 |
| R44G 邊界形狀熱圖 | `results/visual_samples/r44g_boundary_shape_heatmap.png` | 七類顯微結構與所有候選的形狀錯誤熱圖 |
| R44H 主報告 | `reports/R44H_STEPA_FAMILY_AVERAGE.md` | R44H Step 0 / Step A 結果與下一步判斷 |
| R44H Step B 報告 | `reports/R44H_STEPB_REGION_KD.md` | 單一老師局部蒸餾結果與判斷 |
| R44H Step B 計畫 | `reports/R44H_STEPB_REGION_KD_PLAN.md` | Step B 完成標準與 go/no-go 門檻 |
| R44 歷程追溯稽核 | `reports/R44_HISTORY_TRACEABILITY_AUDIT.md` | R39-R44H 文件完整性稽核 |
| R44H Step B 啟動腳本 | `scripts/launch_r44h_stepb.py` | 從 R44B from R42 啟動局部老師蒸餾 |
| R44H Step B 測試 | `tests/test_r44h_region_kd.py`、`tests/test_r44h_stepb_launcher.py` | 局部遮罩損失與啟動器設定測試 |
| R44H Step B checkpoint | `results/r44h_stepb_region_kd/checkpoints/r44h_stepb_region_kd_main_latest.pth.tar` | 短訓練評估權重 |
| R44H Step B 位移摘要 | `results/r44h_stepb_region_kd/r44h_stepb_motion_summary.json` | Step B R44 位移指標 |
| R44H Step B 位移逐項表 | `results/r44h_stepb_region_kd/r44h_stepb_motion_rows.csv` | Step B R44 位移逐 pair 指標 |
| R44H Step B 環形代理 | `results/r44h_stepb_region_kd/r44h_stepb_ring_guard_summary.json` | Step B 本地三尺度環形代理紀錄 |
| R44H Step A 總表 | `results/r44h_family_average/r44h_stepa_summary.csv` | 四個 R44B 家族平均候選的形狀、位移與環形代理彙整 |
| R44H Step A JSON | `results/r44h_family_average/r44h_stepa_summary.json` | 同一份結果的機器可讀版本 |
| R44H 平均候選權重 | `results/r44h_family_average/checkpoints/` | 四個 R44B 家族平均候選 checkpoint |
| R44H 位移分族表 | `results/diagnostics/r44h_family_scorecard.csv` | R44B/R44C/R44H 候選的分族位移與邊界距離 |
| R44H 邊界形狀分族表 | `results/diagnostics/r44h_boundary_shape_scorecard.csv` | R44B/R44C/R44H 候選的邊界形狀分項分數 |
| R44H 目標分族排名 | `results/diagnostics/r44h_boundary_shape_target_rank.csv` | 大區塊與混合場景合併後排名 |
| R44H 本地環形代理 | `results/ring_guard/r44h_*_ring_guard_summary.json` | 四個平均候選的三尺度本地環形代理紀錄 |
| R44B from R42 checkpoint | `results/archive_retained_20260824/training_checkpoints/training_progress_GESR_v1_v5_ST0p8_SWP_r44_motion_from_r42_best_20260506_201801/best_tradeoff.pth.tar` | 主研究候選 |
| R44B from R40 checkpoint | `results/archive_retained_20260824/training_checkpoints/training_progress_GESR_v1_v5_ST0p8_SWP_r44_motion_from_r40_a045_20260506_203143/best_tradeoff.pth.tar` | 對照候選 |
| R44B from COMBO checkpoint | `results/archive_retained_20260824/training_checkpoints/training_progress_GESR_v1_v5_ST0p8_SWP_r44_motion_from_combo_20260506_204231/best_tradeoff.pth.tar` | 保守起點對照 |
| R44C low-motion checkpoint | `results/archive_retained_20260824/training_checkpoints/training_progress_GESR_v1_v5_ST0p8_SWP_r44c_low_motion_static_guard_20260506_230332/latest.pth.tar` | R44C 探針；短訓練使用 latest |
| R44C family-holdout checkpoint | `results/archive_retained_20260824/training_checkpoints/training_progress_GESR_v1_v5_ST0p8_SWP_r44c_family_holdout_motion_20260506_230836/latest.pth.tar` | R44C 探針；短訓練使用 latest |
| R44C static-heavy checkpoint | `results/archive_retained_20260824/training_checkpoints/training_progress_GESR_v1_v5_ST0p8_SWP_r44c_static_heavy_all_motion_20260506_231357/latest.pth.tar` | R44C 最佳探針；D 保留 latest |

## 注意事項

- 文件以繁體中文為主。
- R44 是研究優先，不設環形淘汰線。
- 外部 GMF 仍要記錄，但不作 R44 研究價值否定。
- 若 R44B 只改善 PSNR，卻沒有改善邊界位移、格線相位與小缺陷位置，判定為失敗。
