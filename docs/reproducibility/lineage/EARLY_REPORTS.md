# 早期原JSON與輪次對照

原檔按profile與日誌引用綁定；分數是當時內部選擇量，不能當外部GMF或物理誤差。較早val_batch與較晚seq_val分開，不能跨來源比較分數高低。

| 輪次 | 原時間 | 原profile | sweep／final設定 | 評估來源 | 原狀態 | 原完整JSON |
|---|---|---|---|---|---|---|
| R2 | 20260309_105119 | 較早未寫profile，依Round2日誌綁定 | 6／14 | monitor_shift | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260309_105119.json) |
| R3 | 20260309_115909 | round3_gmf_guard | 6／12 | monitor_shift | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260309_115909.json) |
| R3 | 20260309_124822 | round3_sharp_balance | 6／12 | monitor_shift | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260309_124822.json) |
| R4 | 20260309_134617 | round4_refine_seed | 6／10 | monitor_shift | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260309_134617.json) |
| R3 | 20260309_144411 | round3_gmf_guard | 6／10 | monitor_shift | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260309_144411.json) |
| R3 | 20260309_151919 | round3_sharp_balance | 6／10 | monitor_shift | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260309_151919.json) |
| R5 | 20260309_173251 | round5_extval_preserve | 6／10 | monitor_shift | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260309_173251.json) |
| R5 | 20260309_180937 | round5_extval_data_probe | 6／10 | monitor_shift | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260309_180937.json) |
| R6 | 20260309_204603 | round6_subpixel_guard | 8／12 | monitor_shift | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260309_204603.json) |
| R6 | 20260309_231113 | round6_microstep_probe | 8／12 | monitor_shift | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260309_231113.json) |
| R6 | 20260310_002048 | round6_subpixel_guard | 10／14 | monitor_shift | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260310_002048.json) |
| R6 | 20260310_033006 | round6_microstep_probe | 10／14 | monitor_shift | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260310_033006.json) |
| R6 | 20260310_045457 | round6_subpixel_guard | 8／12 | monitor_shift | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260310_045457.json) |
| R6 | 20260310_071754 | round6_microstep_probe | 8／12 | monitor_shift | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260310_071754.json) |
| R6 | 20260310_110427 | round6_microstep_probe | 4／6 | monitor_shift | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260310_110427.json) |
| R6 | 20260310_113735 | round6_microstep_probe | 4／6 | monitor_shift | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260310_113735.json) |
| R6 | 20260310_120656 | round6_microstep_probe | 4／6 | monitor_shift | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260310_120656.json) |
| R6 | 20260310_142118 | round6_microstep_probe | 4／6 | monitor_shift | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260310_142118.json) |
| R7 | 20260310_154418 | round7_sequence_microstep_probe | 4／6 | monitor_shift | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260310_154418.json) |
| R8 | 20260310_162500 | round8_sequence_refine | 4／6 | monitor_shift | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260310_162500.json) |
| R9 | 20260310_183446 | round9_sequence_val_align | 4／6 | val_batch | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260310_183446.json) |
| R10 | 20260310_183945 | round10_crossscale_seqval | 4／6 | val_batch | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260310_183945.json) |
| R10 | 20260310_184332 | round10_crossscale_seqval | 5／6 | val_batch | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260310_184332.json) |
| R9 | 20260310_184811 | round9_sequence_val_align | 6／6 | val_batch | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260310_184811.json) |
| R9 | 20260310_211729 | round9_sequence_val_align | 4／6 | seq_val | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260310_211729.json) |
| R10 | 20260310_212245 | round10_crossscale_seqval | 4／6 | seq_val | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260310_212245.json) |
| R10 | 20260310_212722 | round10_crossscale_seqval | 5／6 | seq_val | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260310_212722.json) |
| R9 | 20260310_213300 | round9_sequence_val_align | 6／6 | seq_val | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260310_213300.json) |
| R11 | 20260310_233450 | round11_annulus_gmf_align | 1／2 | seq_val | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260310_233450.json) |
| R11 | 20260310_234103 | round11_annulus_gmf_align | 1／2 | seq_val | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260310_234103.json) |
| R11 | 20260310_234951 | round11_annulus_gmf_align | 2／3 | seq_val | ok | [完整設定、候選及選擇](early_sources/reports/auto_tune_report_20260310_234951.json) |

設定final_epochs不證明final實際執行；原final_run及日誌才是依據。NaN、零值、來源修復與失敗均保留原值。

原status=ok只是程式寫入的狀態，不等於外部GMF驗收通過。
