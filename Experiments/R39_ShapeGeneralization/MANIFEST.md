# R39 Shape Generalization Manifest

## 追蹤的實驗檔案

- `README.md` — 實驗目的、路線、執行步驟。
- `scripts/r39_shape_data.py` — 確定性的多形狀資料包 planner / builder。
- `scripts/launch_r39.py` — 兩個訓練候選的 launcher。
- `scripts/run_r39_shape_recon.py` — held-out 形狀資料包的逐 stage 重建 runner。
- `scripts/summarize_r39_shape_recon.py` — held-out 形狀重建的指標彙總器。
- `scripts/run_r39_ring_guard.py` — 包住 720-angle 序列分析的三尺度 local ring guard。
- `scripts/r39_weight_sweep.py` — COMBO ↔ R39 權重平均的 pure logic(驗證、插值、sweet-spot 評估)。
- `scripts/run_r39_weight_sweep.py` — sweep runner,對每個 alpha 串接 shape recon + ring guard,輸出聚合的 trade-off 表。
- `scripts/plot_r39_weight_sweep.py` — 從聚合的 sweep JSON 畫 `sweep_tradeoff.png`。
- `scripts/r39_external_compare.py` — 外部 GMF 比較器:parse `GMF_score.txt`、用 `|z|>5` outlier filter 算 step_std、產出 `R39_EXTERNAL_COMPARE.md` 與 `external_compare_summary.json`。
- `scripts/r39_a030_microscopy_evaluation.py` — a030 在多樣顯微圖形上的詳細評估（PSNR / SSIM / HF / Edge / Contrast / 邊界 F1 / R44G 形狀錯誤分數），跨 R39 shape_val_unseen 與 R40 micro_val_unseen 兩個資料集，重用既有重建。
- `scripts/r39_a030_eval_add_r40_a045.py` — 補測腳本:把 R40 a045 拉進來作三方對比（COMBO / a030 / R40 a045），合併進主評估報告。
- `scripts/r39r40_complementary_average.py` — R39 a030 × R40 a043 跨輪權重平均腳本，產生 α=0.25 / 0.5 / 0.75 中間 checkpoint。
- `scripts/r39r40_a025_capability_eval.py` — R39R40_avg_a025 全方位能力評估腳本，含 R40 micro_val_unseen 跟 R39 shape_val_unseen 詳細指標、視覺四項統計，產出 capability_eval 報告。
- `scripts/r39r40_a025_four_panel_contact.py` — R40 micro_val_unseen 上 GT / COMBO / a030 / a025 四聯對比 sheet。
- `scripts/r39r40_a025_visual_compare.py` — R40 micro + R39 shape 五聯對比 sheet（GT / COMBO / a030 / a043 / a025）。
- `tests/test_r39_shape_data.py` — 資料包配對、held-out split 隔離、manifest 建立的單元測試。
- `tests/test_r39_ring_guard.py` — ring guard 資料集挑選與 compact summary 的單元測試。
- `tests/test_r39_weight_sweep.py` — 權重 sweep pure logic 單元測試。
- `tests/test_r39_external_compare.py` — 外部 GMF 比較 pure logic 的單元測試(parser、step_std + outlier filter、verdict tier)。
- `reports/R39_RESULTS.md` — 目前狀態與升級檢核清單。
- `reports/R39_EXTERNAL_COMPARE.md` — a030 的外部 GMF 比較正式報告(自動產生,要重跑就執行 `scripts/r39_external_compare.py`)。
- `reports/R39_A030_MICROSCOPY_EVALUATION.md` — a030 在多樣顯微圖形上的詳細評估報告，含 R40 a045 三方補測對比（2026-05-10 整合，事實描述為主，不下 verdict）。
- `results/a030_x_a043_sweep/reports/R39R40_COMPLEMENTARY_AVG_RESULTS.md` — R39 a030 × R40 a043 跨輪權重平均 5 點 sweep 結果報告，含外部 GMF 數字、trade-off 模式、α=0.25 PASS_UPGRADE_GUARD 紀錄。
- `results/a030_x_a043_sweep/reports/R39R40_AVG_a025_CAPABILITY_EVAL.md` — R39R40_avg_a025 全方位能力評估報告（顯微/形狀/視覺四項/五聯對比），2026-05-11 升級依據。
- `results/a030_x_a043_sweep/reports/R39R40_AVG_a025_EXTERNAL_COMPARE.md` — α=0.25 外部 GMF 解析報告（r40_external_compare.py 產出）。
- `results/a030_x_a043_sweep/reports/R39R40_AVG_a050_EXTERNAL_COMPARE.md` — α=0.5 同上。
- `results/a030_x_a043_sweep/reports/R39R40_AVG_a075_EXTERNAL_COMPARE.md` — α=0.75 同上。
- `results/.gitkeep` — 為未來 R39 結果留位置用。
- `results/shape_recon/shape_val_unseen_combo_baseline_summary.json` — held-out 形狀集的 COMBO baseline 彙總。
- `results/shape_recon/shape_val_unseen_r39_shape_mix_safe_summary.json` — safe 候選的 held-out 形狀彙總。
- `results/shape_recon/shape_val_unseen_r39_shape_mix_strong_summary.json` — strong 候選的 held-out 形狀彙總。
- `results/shape_recon/r39_representative_shape_sheet.png` — 代表性視覺對比圖。
- `results/ring_guard/r39_shape_mix_safe_ring_guard_summary.json` — safe 候選的 local ring guard 彙總。
- `results/ring_guard/r39_shape_mix_strong_ring_guard_summary.json` — strong 候選的 local ring guard 彙總。
- `results/weight_sweep/sweep_summary.json` — 聚合的權重平均 sweep + sweet-spot verdict。
- `results/weight_sweep/sweep_summary.md` — 給人看的 trade-off 表。
- `results/weight_sweep/sweep_tradeoff.png` — shape PSNR vs alpha 與三尺度 ring step_std vs alpha 的圖。
- `results/weight_sweep/shape_recon/<alpha_tag>_shape_summary.json` — 各 alpha 的形狀驗證彙總。
- `results/weight_sweep/ring_guard/<alpha_tag>_ring_guard_summary.json` — 各 alpha 的 local ring guard 彙總。
- `results/external_gmf_a030/pitch{8px,0p8px,0p08px}/GMF_score.txt` — alpha=0.30 平均 checkpoint 在三個正式尺度上的外部 GMF 工具輸出。
- `results/external_gmf_a030/external_compare_summary.json` — parse 過的外部 GMF step_std + verdict。
- `results/a030_microscopy_eval/per_pair_metrics.csv` — a030 / COMBO / R40 a045 三候選在 R39 shape_val_unseen 與 R40 micro_val_unseen 上的逐張指標。
- `results/a030_microscopy_eval/stage_summary.csv` — 逐資料集逐 stage 平均。
- `results/a030_microscopy_eval/overall_summary.csv` — 每候選每資料集整體平均。
- `results/a030_microscopy_eval/delta_three_*.csv` — 三方對比的 PSNR / 邊界 F1 / 形狀錯誤逐 stage pivot 表（R39 shape 與 R40 micro 各自一份）。
- `results/a030_microscopy_eval/cross_dataset_headline.json` — 跨資料集 headline 整理。
- `results/a030_microscopy_eval/visuals/contact_sheet_r40.png` — R40 5 stage × 4 frame 三聯對比 sheet（GT / COMBO / a030）。
- `results/a030_microscopy_eval/r40_a045_on_shape/reconstruct_progress_*` — R40 a045 在 R39 shape_val_unseen 的補跑重建（2026-05-10 inference，timestamp `20260504_174058`，七個 stage 各一個子目錄）。
- `results/a030_x_a043_sweep/checkpoints/{a025,a050,a075}/best_tradeoff.pth.tar` — R39 a030 × R40 a043 在三個中間 α 的平均 checkpoint（升級候選 a025 的 checkpoint 在此）。
- `results/a030_x_a043_sweep/external_recon/{a025,a050,a075}/reconstruct_progress_*` — 三個中間 α 的外部三尺度 ring 重建（送外部 GMF 用）。
- `results/a030_x_a043_sweep/external_recon/{a025,a050,a075}/external_gmf/pitch{8px,0p8px,0p08px}/GMF_score.txt` — 外部 GMF 視覺定位工具回傳的 step_std 來源檔。
- `results/a030_x_a043_sweep/external_recon/{a025,a050,a075}/external_compare_summary.json` — r40_external_compare.py 解析後的三尺度 step_std + delta + verdict。
- `results/a030_x_a043_sweep/micro_recon/a025/reconstruct_progress_*` — a025 在 R40 micro_val_unseen 的重建（5 stage 各 20 對）。
- `results/a030_x_a043_sweep/shape_recon/{a025,a043}/reconstruct_progress_*` — a025 跟 R40 a043 在 R39 shape_val_unseen 的重建（7 stage 各 30 對）。
- `results/a030_x_a043_sweep/capability_eval/per_pair_metrics.csv` — a025 四方對照（COMBO / a030 / a043 / a025）逐張指標。
- `results/a030_x_a043_sweep/capability_eval/stage_summary.csv` — 逐 stage 平均。
- `results/a030_x_a043_sweep/capability_eval/overall_summary.csv` — 整體平均。
- `results/a030_x_a043_sweep/capability_eval/visual_stats.csv` — 視覺四項（gradient magnitude / edge steepness / contrast / edge contrast）每 pitch frame-wise mean。
- `results/a030_x_a043_sweep/capability_eval/capability_summary.json` — 上述彙總 JSON 版。
- `results/a030_x_a043_sweep/visuals/contact_sheet_a025_four_panel.png` — GT / COMBO / a030 / a025 四聯 sheet（cell 320，5 顯微類 × 4 frame）。
- `results/a030_x_a043_sweep/visuals/contact_sheet_a025_micro_five_panel.png` — R40 micro 五聯 sheet（含 a043）。
- `results/a030_x_a043_sweep/visuals/contact_sheet_a025_shape_five_panel.png` — R39 shape 五聯 sheet（含 a043）。
- `results/a030_x_a043_sweep/README.md` — sweep dispatch 說明（怎麼把 BMP 送外部 GMF、怎麼解析 GMF_score.txt）。
- `results/synthetic_microscopy_demo/gt/0001.bmp` — 為「訓練分布限制」這個發現手做的合成 IC 風格 GT。
- `results/synthetic_microscopy_demo/input/0001.bmp` — PSF blur + Poisson-Gaussian noise 後的輸入(使用 lighter-noise 版,alpha=160, sigma=1.0)。
- `results/synthetic_microscopy_demo/comparison.png` — 4 連格並列(GT / blurred / COMBO recon / a030 recon)。
- `results/synthetic_microscopy_demo/_view_{gt,input,combo,a030,train_complex_GT,train_complex_INP}.png` — 各個獨立 panel,含一張訓練分布內的樣本當視覺對照。

## Git 之外產生的檔案

- `Training_Data/r39_shape_generalization/r39_shape_mix_safe/`
- `Training_Data/r39_shape_generalization/r39_shape_mix_strong/`
- `Training_Data/r39_shape_generalization/shape_val_unseen/`

這些是產生出來的資料包,內含影像 copy 或 hardlink 加上 `manifest.json`。可以從上面的 script 重建。

`results/shape_recon/` 底下的重建影像資料夾是 local 產出。彙總用的 JSON 才是入庫紀錄。

`results/ring_recon/` 的 ring 重建影像資料夾與 `results/ring_guard/*_sequence_analysis/` 的詳細序列分析輸出也是 local 產出。compact 的 ring guard JSON 才是入庫紀錄。

權重 sweep 產生的中間檔(可從 sweep runner 重建,不入 git):

- `results/weight_sweep/checkpoints/a000/...a100/best_tradeoff.pth.tar` — 11 個插值 checkpoint(每個約 20 MB,共約 220 MB)
- `results/weight_sweep/shape_recon/<alpha_tag>/reconstruct_progress_*` — 各 alpha 的形狀重建
- `results/weight_sweep/ring_recon/<alpha_tag>/reconstruct_progress_*` — 各 alpha 的三尺度 ring 重建(被選中的 alpha 會送進外部 GMF)
- `results/weight_sweep/ring_guard/<alpha_tag>_sequence_analysis/` — 各 alpha 的 720-angle 序列分析輸出
- `results/weight_sweep/_step2_alpha050.log`, `_full_sweep.log` — 執行 log
- `results/synthetic_microscopy_demo/recon_a030/` 與 `recon_combo/` — 對合成 microscopy GT 的逐 checkpoint 重建(可從 `gt/0001.bmp` 重新推得)
