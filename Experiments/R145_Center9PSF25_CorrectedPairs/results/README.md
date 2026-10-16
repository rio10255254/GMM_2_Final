# R145 結果存放

修正方向後的 768 組配對、8192 次訓練、930 張重建與 8370 顆圓量測均已完成。`preflight.json` 保存新 PSF 來源、資料對照及網路機制檢查；`reconstruction/` 是指向 H 槽的連結，保存全部實拍浮點影像及逐張收據；`centers/` 和 `comparison/` 保存同讀法量測與模型比較。`position_stability_followup.json` 保存逐顆圓的重拍檢查；`cli_replay/` 保存單張推論的逐值重播。`deep_diagnosis/` 保存後驗光學運算、PSF 可辨識訊號、拍攝條件和細位移檢查。最終核對見 `final_audit.json`，正式解讀以 `../reports/R145_RESULTS.md`、`../reports/R145_STABILITY_FOLLOWUP.md` 和 `../reports/R145_PSF_LIMITING_MECHANISMS.md` 為準。
