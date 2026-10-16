# R143 結果存放

`preflight.json` 為資料與模型檢查。`reconstruction/` 是指向 H 槽的連結，存放全部實拍重建及逐張收據。`centers/` 與 `comparison/` 存放本輪量測及和既有方法的相同流程比較。完整結果以 `../reports/R143_RESULTS.md` 為準。

資料本身的改動見 `data_effect_audit.json` 與 `training_pair_preview.png`；PSF 可辨識性見 `oracle_psf_identifiability.json` 及 `selector_evaluation.json`；真實影像的後驗 PSF 敏感度見 `real_psf_effect.json`。`final_audit.json` 核對全流程完成，`cli_replay_check.json` 證明單張推論入口可重現正式結果。H 槽完整影像是活動結果，保留原始浮點值；此處 D 槽保存主要查核及代表圖。

`stability_diagnosis/` 保存後續位移與尺寸穩定性審查的來源讀數、受控擾動結果、`summary.json` 及圖表所需的表格。正式解讀以 `../reports/R143_STABILITY_DIAGNOSIS.md` 為準。
