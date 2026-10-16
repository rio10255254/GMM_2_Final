# R116_CoherentGeometryAnchorScratch 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

沿輪廓保持位移／寬度一致並限制細節

修復BF16錯誤後重新從零；E42主要、E24備選、E48未採用，GMF仍缺回傳

## 必要來源

兩段訓練、精度修復、E42／E24／E48及固定驗證資料

## 影像保存

36顆粗輪廓改善、周長／位移代價及錯誤點

## 原始報告

- [R116_ARCHITECTURE_DECISION_ZH.md](reports/R116_ARCHITECTURE_DECISION_ZH.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [data/prepare_dataset.py](data/prepare_dataset.py)
- [inference/__init__.py](inference/__init__.py)
- [inference/tiled.py](inference/tiled.py)
- [model/__init__.py](model/__init__.py)
- [model/r116_model.py](model/r116_model.py)
- [probes/analyze_counterfactuals.py](probes/analyze_counterfactuals.py)
- [probes/analyze_probe_activation.py](probes/analyze_probe_activation.py)
- [probes/diagnose_formal_failure.py](probes/diagnose_formal_failure.py)
- [probes/r109_counterfactuals.py](probes/r109_counterfactuals.py)
- [probes/stress_width_numerics.py](probes/stress_width_numerics.py)
- [scripts/benchmark_training.py](scripts/benchmark_training.py)
- [scripts/finalize_design.py](scripts/finalize_design.py)
- [scripts/launch_calibration_background.ps1](scripts/launch_calibration_background.ps1)
- [scripts/launch_formal_background.ps1](scripts/launch_formal_background.ps1)
- [scripts/monitor_training.ps1](scripts/monitor_training.ps1)
- [scripts/run_probe.ps1](scripts/run_probe.ps1)
- [scripts/start_formal_training.ps1](scripts/start_formal_training.ps1)
- [scripts/validate_architecture.ps1](scripts/validate_architecture.ps1)
- [tests/test_dataset.py](tests/test_dataset.py)
- [tests/test_losses.py](tests/test_losses.py)
- [tests/test_model.py](tests/test_model.py)
- [tests/test_profile_targets.py](tests/test_profile_targets.py)
- [tests/test_trainer.py](tests/test_trainer.py)
- [tests/test_validation_adapter.py](tests/test_validation_adapter.py)
- [training/__init__.py](training/__init__.py)
- [training/continue_calibration.py](training/continue_calibration.py)
- [training/dataset.py](training/dataset.py)
- [training/losses.py](training/losses.py)
- [training/profile_targets.py](training/profile_targets.py)
- [training/smoke_train.py](training/smoke_train.py)
- [training/train.py](training/train.py)
- [validation/__init__.py](validation/__init__.py)
- [validation/adapter.py](validation/adapter.py)
- [validation/audit_and_select.py](validation/audit_and_select.py)
- [validation/build_external_gmf_e42.py](validation/build_external_gmf_e42.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R116_CoherentGeometryAnchorScratch.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
