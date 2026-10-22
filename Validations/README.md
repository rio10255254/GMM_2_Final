# 交付包當時的核對紀錄

這裡保存部署、分塊推論和資料生成交付的原核對程式與紀錄。它們證明各自包與當時列出的條件，不代表重跑全部研究，也不自動提升模型身分。

| 內容 | 入口 |
|---|---|
| JunHua ONNX原檢查 | [原說明](MOSR_ONNX_JunHua/README.md)、[原報告](MOSR_ONNX_JunHua/report.md) |
| R61原部署包 | `R61_ONNX_Package_20260808/`，使用原包的版本與環境 |
| R61分塊GPU升級 | `R61_ONNX_TilingUpgrade_20260817/`；接縫表現與全圖量測相同是不同主張 |
| R61生成包清理後取回 | [當次實際重建與來源](R61_TrainingData_Regenerator_20261004/CLEANUP_AND_REBUILD_20261021.md) |

要使用交付先從[交付總入口](../Deliverables/README.md)讀對應包，不批次啟動本區所有程式。
