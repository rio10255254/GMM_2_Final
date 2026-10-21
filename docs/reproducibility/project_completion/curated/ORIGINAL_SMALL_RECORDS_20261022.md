# 三份原小型紀錄的閱讀補件

本次閱讀入口檢查找到三份原先由本機路徑引用、但未直接放在GitHub一般檔案裡的小型JSON，合計3,996 bytes。這次保存原位元組；沒有重算、改寫原欄位、生成影像、訓練或推論，也沒有改變論文或模型採用判決。

| 原紀錄 | 原本記錄什麼 | 如何解讀 |
|---|---|---|
| [R146資料與訓練鏈核對](../../../../Experiments/R146_SEMCoreHaloPSF25_MatchedPairs/results/data_training_chain_audit.json) | 2026-09-25原核對：768組清楚目標沿用R145，原來源／銀行／模型身分、692組模糊與76組清楚對照、原8,192次順序核對。 | 這是原先完成的來源檢查，不是本次再次重播；R146實拍輪廓／尺寸較差的結果仍見[原結果](../../../../Experiments/R146_SEMCoreHaloPSF25_MatchedPairs/reports/R146_RESULTS.md)與[因果審查](../../../../Experiments/R146_SEMCoreHaloPSF25_MatchedPairs/reports/R146_CAUSAL_AUDIT.md)。 |
| [R148架構停止紀錄](../../../../Experiments/R148_MeasurementStableNativePSF/results/architecture_audit.json) | 2026-09-26原核對：反覆使用網路與光學運算，累積所需範圍超出原訓練裁切邊界；原正式程序只有62列，沒有正式保存模型，舊進行中標記過時。 | 保留原未通過及不續跑判決；理論最壞範圍是保守界線，不能只靠大範圍數字宣稱全部實際影像皆有同等邊界誤差。[原架構審查](../../../../Experiments/R148_MeasurementStableNativePSF/reports/R148_ARCHITECTURE_REVIEW.md)。 |
| [SwinIR原訓練完成紀錄](../../../../Experiments/R153_MeanExternalBenchmark/runs/launcher_logs/SwinIR_training_complete_verified_20261007.json) | 2026-10-07早上：8輪／4,096次更新、依合成驗證選第8輪EMA、固定模型身分及128個合成測試場景。 | 其中real_validation_still_pending是當天早上的階段狀態；當天下午已完成十方法實拍比較，現在應讀[最後交接與完整結果](../../../../Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md)。它不是目前仍在等待驗證的宣稱。 |

較早入口引用的原大型ZIP保留本機名稱，GitHub閱讀連結改接已保存的方法／結果文件；沒有為了修連結而上傳整套訓練資料或大型圖庫。固定2026-10-21精選保存版保持原內容；這是後來的閱讀補件。
