# R85_R79SharedCanvasOpticalRepair 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

以共同光學畫布保留R79能力

切片一致但邊界超過限制，不開啟新的確認資料

## 必要來源

原R79、生成配方、兩個篩選模型及未開封狀態

## 影像保存

切片成功與邊界退步對照

## 原始報告

- [README.md](README.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [inference/infer_r85.py](inference/infer_r85.py)
- [model/GeoEdgeAlignSR_v1_ModelA_v5_NoCoord.py](model/GeoEdgeAlignSR_v1_ModelA_v5_NoCoord.py)
- [scripts/lock_training_subset.py](scripts/lock_training_subset.py)
- [scripts/r85_dataset.py](scripts/r85_dataset.py)
- [scripts/screen_checkpoints.py](scripts/screen_checkpoints.py)
- [training/train_r85.py](training/train_r85.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R85_R79SharedCanvasOpticalRepair.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
