> **最新結果判讀**：R139 完整執行但訓練早期輸出飽和，最後基本等同原圖，不能採用。請先讀 [因果審查](reports/R139_CAUSAL_AUDIT.md)，再看原始數值 [結果表](reports/R139_RESULTS.md)。流程完成不等於模型有效。

# R139 正式執行導覽

本模型已由原型轉入正式訓練流程。先讀 [本輪訓練與量測條件](FORMAL_RUN.md)；原型推導另在 [早期架構說明](README.md)。

執行中看 `runs/formal_8192/status.json` 與 `runs/pipeline_status.json`，或執行 `MONITOR_R139.cmd`。結果只有在全部訓練、重建、量測及查核完成後才由 `reports/R139_RESULTS.md` 發布。舊原型說明中「尚未正式訓練」是建立原型當日的快照，不代表此新執行流程的即時狀態。
