# R61 驗證輸出已清理，原訓練資料保留

本次只移除這裡的 generated 與 generated_v2 兩套大型測試產物。真正訓練使用的資料、完整交付包、兩版測試來源、獨立測試環境，以及本資料夾原成功／失敗報告都保留。

第一次原始生成器有15份舊幾何標記不同；原失敗檔、修正後對照、兩份完整資料描述及原檢查報告已保存於：
H:\GMM_2_Final_Archive\validation_history\R61_Regenerator_20261004_cleanup_20261021

固定歷史版本依原來源重建的114,283檔相同證據仍是原日期的 full_rebuild_check.json。這是在核對當年使用的版本，不據此判斷哪份標記在物理上比較準。本輪沒有重新產生整套資料或重新訓練，也不能把本輪來源核對寫成新的完整重建實驗。

若要重新生成，請使用完整交付包的 regenerate_r61.py，指定新的輸出與報告位置，不覆寫本資料夾原報告。例如從專案根目錄執行：

```powershell
C:\Users\Rio\anaconda3\python.exe Deliverables/R61_TrainingData_Regenerator_20261004/regenerate_r61.py --output-root D:\R61_Rebuilt_New --report D:\R61_Rebuilt_New\rebuild_check.json
```

來源包仍在 Deliverables/R61_TrainingData_Regenerator_20261004；實際訓練庫仍在 Thesis_MOSR_Evidence/LabSystem_MOSR/Training_Data/r61_universal_boundary_generalization/hs100mg_basler/r61_universal_boundary_train_motion_texture_step_guard_v16。

[一個原影像與標記對照](../../docs/reproducibility/r61_regeneration_example/README.md)說明為什麼除了生成程式，仍須保留部分早期來源。
