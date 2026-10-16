# R84_R79TileStableRootRepair 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

移除R79對看到範圍的依賴

R84到86各修復均有代價，最後保留精確R79並固定全圖

## 必要來源

原R79與三種修復設定、固定形狀／SEM／位移資料

## 影像保存

切片差異與修復後形狀損失同時展示

## 原始報告

- [R79_ROOT_REPAIR_CLOSEOUT.md](reports/R79_ROOT_REPAIR_CLOSEOUT.md)
- [R84_FINAL_VERDICT.md](reports/R84_FINAL_VERDICT.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [.gitignore](.gitignore)
- [inference/infer_r84.py](inference/infer_r84.py)
- [model/GeoEdgeAlignSR_v1_ModelA_v5_NoCoord.py](model/GeoEdgeAlignSR_v1_ModelA_v5_NoCoord.py)
- [model/GeoEdgeAlignSR_v1_Utils.py](model/GeoEdgeAlignSR_v1_Utils.py)
- [scripts/analyze_final_confirmation.py](scripts/analyze_final_confirmation.py)
- [scripts/evaluate_final_real_motion.py](scripts/evaluate_final_real_motion.py)
- [scripts/make_delivery_parity_qa.py](scripts/make_delivery_parity_qa.py)
- [scripts/prepare_final_confirmation.py](scripts/prepare_final_confirmation.py)
- [scripts/prepare_preconditioner_sem_sweep.py](scripts/prepare_preconditioner_sem_sweep.py)
- [scripts/probe_shared_global_preconditioner.py](scripts/probe_shared_global_preconditioner.py)
- [scripts/probe_zero_shot.py](scripts/probe_zero_shot.py)
- [scripts/r84_dataset.py](scripts/r84_dataset.py)
- [scripts/screen_formal_checkpoints.py](scripts/screen_formal_checkpoints.py)
- [scripts/screen_pilots.py](scripts/screen_pilots.py)
- [scripts/sweep_shared_preconditioner_strength.py](scripts/sweep_shared_preconditioner_strength.py)
- [scripts/validate_r79_fullframe_parity.py](scripts/validate_r79_fullframe_parity.py)
- [tests/test_r79_fullframe_delivery.py](tests/test_r79_fullframe_delivery.py)
- [training/train_r84.py](training/train_r84.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R84_R79TileStableRootRepair.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
