# R117_CenterLockedSubpixelScratch 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

保留必要法線位移並避免寬度造成額外中心移動

來源是8倍生成後積分，不用實體答案或舊權重

## 必要來源

本輪生成、被固定的成像形成順序及正式模型

## 影像保存

中心與寬度互相影響的控制及實體失敗

## 原始報告

- [README.md](README.md)
- [FINDINGS.md](analysis/design_audit_20260905/FINDINGS.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [analysis/design_audit_20260905/build_companion.py](analysis/design_audit_20260905/build_companion.py)
- [analysis/design_audit_20260905/diagnose.py](analysis/design_audit_20260905/diagnose.py)
- [analysis/design_audit_20260905/preview_source_audit.py](analysis/design_audit_20260905/preview_source_audit.py)
- [analysis/design_audit_20260905/render_mechanism_audit.py](analysis/design_audit_20260905/render_mechanism_audit.py)
- [data/geometry.py](data/geometry.py)
- [data/prepare_dataset.py](data/prepare_dataset.py)
- [inference/tiled.py](inference/tiled.py)
- [model/r117_model.py](model/r117_model.py)
- [scripts/launch_formal_background.ps1](scripts/launch_formal_background.ps1)
- [scripts/monitor_training.ps1](scripts/monitor_training.ps1)
- [scripts/prepare_data.ps1](scripts/prepare_data.ps1)
- [scripts/smoke_test.ps1](scripts/smoke_test.ps1)
- [scripts/start_formal_training.ps1](scripts/start_formal_training.ps1)
- [tests/test_architecture.py](tests/test_architecture.py)
- [training/dataset.py](training/dataset.py)
- [training/losses.py](training/losses.py)
- [training/train.py](training/train.py)
- [validation/validate_pretraining.py](validation/validate_pretraining.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R117_CenterLockedSubpixelScratch.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
