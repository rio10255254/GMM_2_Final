# R140v2 使用入口

先讀 [固定訓練及驗證規格](FORMAL_RUN.md)、[R139 失敗原因](../R139_UNetRecurrentPrototype/reports/R139_CAUSAL_AUDIT.md) 和 `config/PRELAUNCH_CORRECTION.json`。本包是 R140 來源鎖定失敗後另立的可追溯版本。短測、正式訓練和真實影像驗證的狀態分開記錄，不能只憑程序完成就宣稱模型有效。

完整流程由 `formal/launch.py` 啟動。單獨的前景進度顯示為 `formal/monitor.py`，關閉顯示不會停止訓練。正式啟動前先執行 `formal/preflight.py`；若校驗失敗，要查原因並另立版本，不能接受新雜湊覆蓋舊證據。

訓練後模型在 `runs/formal_8192/checkpoints/step08192.pth`，實拍輸出在 `results/reconstruction`，量測表格及圖在 `results/comparison` 和 `reports`。這些檔案只有在實際完成相應階段後才存在。
