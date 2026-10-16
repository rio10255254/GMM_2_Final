# R114_ConfidenceGatedRecoverableScratch 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

依R113修復控制塌縮與可恢復細節

短探針與正式訓練必須分開，舊模型只能作機制檢查

## 必要來源

組成感知資料清單、控制／幾何／細節各探針及正式紀錄

## 影像保存

控制是否生效、清楚輸入與最差失敗

## 原始報告

- [R114_EXECUTION_LEDGER_ZH.md](reports/R114_EXECUTION_LEDGER_ZH.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [inference/tiled_runtime.py](inference/tiled_runtime.py)
- [model/__init__.py](model/__init__.py)
- [model/full_model.py](model/full_model.py)
- [model/r114_model.py](model/r114_model.py)
- [model/r114_split_profile_model.py](model/r114_split_profile_model.py)
- [model/test_full_model.py](model/test_full_model.py)
- [model/test_r114_model.py](model/test_r114_model.py)
- [model/test_r114_split_profile_model.py](model/test_r114_split_profile_model.py)
- [probes/controller/analyze.py](probes/controller/analyze.py)
- [probes/controller/diagnose_targets.py](probes/controller/diagnose_targets.py)
- [probes/profile_failure/diagnose_e24.py](probes/profile_failure/diagnose_e24.py)
- [probes/profile_failure/diagnose_r114c_e24.py](probes/profile_failure/diagnose_r114c_e24.py)
- [probes/profile_failure/validate_diagnosis.py](probes/profile_failure/validate_diagnosis.py)
- [probes/profile_failure/validate_r114c_e24_diagnosis.py](probes/profile_failure/validate_r114c_e24_diagnosis.py)
- [probes/r114d_action_selector/__init__.py](probes/r114d_action_selector/__init__.py)
- [probes/r114d_action_selector/adapter.py](probes/r114d_action_selector/adapter.py)
- [probes/r114d_action_selector/evaluate.py](probes/r114d_action_selector/evaluate.py)
- [probes/r114d_action_selector/losses.py](probes/r114d_action_selector/losses.py)
- [probes/r114d_action_selector/model.py](probes/r114d_action_selector/model.py)
- [probes/r114d_action_selector/run_locked_acm.py](probes/r114d_action_selector/run_locked_acm.py)
- [probes/r114d_action_selector/run_short_probe.ps1](probes/r114d_action_selector/run_short_probe.ps1)
- [probes/r114d_action_selector/smoke.py](probes/r114d_action_selector/smoke.py)
- [probes/r114d_action_selector/targets.py](probes/r114d_action_selector/targets.py)
- [probes/r114d_action_selector/test_evaluator_adapter.py](probes/r114d_action_selector/test_evaluator_adapter.py)
- [probes/r114d_action_selector/test_selector.py](probes/r114d_action_selector/test_selector.py)
- [probes/r114d_action_selector/trainer.py](probes/r114d_action_selector/trainer.py)
- [probes/r114e_decoupled_hybrid/__init__.py](probes/r114e_decoupled_hybrid/__init__.py)
- [probes/r114e_decoupled_hybrid/adapter.py](probes/r114e_decoupled_hybrid/adapter.py)
- [probes/r114e_decoupled_hybrid/evaluate.py](probes/r114e_decoupled_hybrid/evaluate.py)
- [probes/r114e_decoupled_hybrid/headroom.py](probes/r114e_decoupled_hybrid/headroom.py)
- [probes/r114e_decoupled_hybrid/losses.py](probes/r114e_decoupled_hybrid/losses.py)
- [probes/r114e_decoupled_hybrid/model.py](probes/r114e_decoupled_hybrid/model.py)
- [probes/r114e_decoupled_hybrid/run_locked_acm.py](probes/r114e_decoupled_hybrid/run_locked_acm.py)
- [probes/r114e_decoupled_hybrid/run_short_probe.ps1](probes/r114e_decoupled_hybrid/run_short_probe.ps1)
- [probes/r114e_decoupled_hybrid/smoke.py](probes/r114e_decoupled_hybrid/smoke.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R114_ConfidenceGatedRecoverableScratch.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
