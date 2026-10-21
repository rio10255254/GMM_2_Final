# R100_CausalOperatorScratch 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

在原有形狀上加入輪廓外程序紋理

本輪40輪獨立模型與設計前測分開

## 必要來源

1250場景／5000觀測、線上紋理配方與實際40輪設定

## 影像保存

輪廓／紋理及各倍率同區域對照

## 原始報告

- [README.md](README.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [Start_R100_Training.cmd](Start_R100_Training.cmd)
- [analysis/analyze_source_supported_detail.py](analysis/analyze_source_supported_detail.py)
- [analysis/run_activation_ablation.py](analysis/run_activation_ablation.py)
- [analysis/run_learnability_probe.py](analysis/run_learnability_probe.py)
- [analysis/run_texture_operator_sweep.py](analysis/run_texture_operator_sweep.py)
- [inference/reconstruct.py](inference/reconstruct.py)
- [inference/run_inference.py](inference/run_inference.py)
- [model/r100_model.py](model/r100_model.py)
- [scripts/analyze_posttraining_internal.py](scripts/analyze_posttraining_internal.py)
- [scripts/calibrate_training_speed.py](scripts/calibrate_training_speed.py)
- [scripts/evaluate_posttraining_holdout.py](scripts/evaluate_posttraining_holdout.py)
- [scripts/evaluate_posttraining_real.py](scripts/evaluate_posttraining_real.py)
- [scripts/evaluate_posttraining_sem_contour.py](scripts/evaluate_posttraining_sem_contour.py)
- [scripts/monitor_training.ps1](scripts/monitor_training.ps1)
- [scripts/start_formal_training.ps1](scripts/start_formal_training.ps1)
- [scripts/start_recovery_training.ps1](scripts/start_recovery_training.ps1)
- [tests/test_r100_contract.py](tests/test_r100_contract.py)
- [training/run_full_training.py](training/run_full_training.py)
- [training/run_recovery_training.py](training/run_recovery_training.py)
- [training/train_r100.py](training/train_r100.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R100_CausalOperatorScratch.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
