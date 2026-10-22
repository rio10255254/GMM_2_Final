# 全專案操作、量測與恢復工具

先決定要讀研究、量測還是取回資料，再用對應工具。這不是一份全部依序執行的腳本清單。

| 工作 | 正確入口 |
|---|---|
| 專案狀態與既有規則 | [目前狀態](../PROJECT_STATE.md)、`project_control_center.py` |
| 位移演算法與原方法 | [位移分析區](Displacement_Algorithms/README.md) |
| 從原表重算數字 | [小型結果包與使用方法](../docs/reproducibility/ASSET_GUIDE.md)；R93、四輪、Lab、光學、十方法各用各自固定入口 |
| 取回相機原拍 | [共用原拍說明](../Shared_Sources/PI_Repeatability_20260903/README.md) |
| 取回特定模型或來源 | [附件指南](../docs/reproducibility/ASSET_GUIDE.md)、[模型指南](../docs/reproducibility/MODEL_GUIDE.md) |
| 維護資料與容量 | [操作規則](../docs/operations/README.md)；讀原恢復清單並保護已有檔案 |

`plan_research_*`、`publish_research_batch.py`、`assemble_verified_archive_collection.py`等保留舊保存工作的程式來源，**不是目前的全量上傳工作**。使用者已停止完整鏡像方案，不能把它們整批重啟。與研究無關的個人工具不列為研究重做依賴。

`tests`保留已有工具測試；原研究結果、模型與資料來源仍由各輪正式報告及清單定義。
