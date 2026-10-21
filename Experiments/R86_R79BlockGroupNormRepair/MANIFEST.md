# R86_R79BlockGroupNormRepair 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

固定小區塊統計以消除切片差異

免訓練測試未過形狀門檻，沒有正式訓練模型

## 必要來源

精確R79及區塊修正程式、原參照讀值

## 影像保存

原版／修正版與已知答案比較

## 原始報告

- [README.md](README.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [inference/infer_r86.py](inference/infer_r86.py)
- [model/GeoEdgeAlignSR_v1_ModelA_v5_NoCoord.py](model/GeoEdgeAlignSR_v1_ModelA_v5_NoCoord.py)
- [scripts/probe_zero_shot.py](scripts/probe_zero_shot.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R86_R79BlockGroupNormRepair.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
