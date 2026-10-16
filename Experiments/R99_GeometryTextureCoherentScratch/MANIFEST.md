# R99_GeometryTextureCoherentScratch 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

把亮暗、幾何、邊緣與紋理動作依序分開

實際41輪停止；保留與計畫48輪的差別

## 必要來源

R92固定來源、線上增補、41輪實際記錄

## 影像保存

幾何與紋理是否同時改善，以及失敗尾端

## 原始報告

- [README.md](README.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [Start_R99_Training.cmd](Start_R99_Training.cmd)
- [analysis/broad_real_probe.py](analysis/broad_real_probe.py)
- [analysis/deep_dive_r99.py](analysis/deep_dive_r99.py)
- [analysis/response_probe.py](analysis/response_probe.py)
- [analysis/synthetic_stage_counterfactual.py](analysis/synthetic_stage_counterfactual.py)
- [analysis/transport_target_audit.py](analysis/transport_target_audit.py)
- [inference/reconstruct.py](inference/reconstruct.py)
- [model/r99_model.py](model/r99_model.py)
- [scripts/calibrate_training_speed.py](scripts/calibrate_training_speed.py)
- [scripts/monitor_training.ps1](scripts/monitor_training.ps1)
- [scripts/start_formal_training.ps1](scripts/start_formal_training.ps1)
- [tests/test_r99_contract.py](tests/test_r99_contract.py)
- [training/run_full_training.py](training/run_full_training.py)
- [training/train_r99.py](training/train_r99.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R99_GeometryTextureCoherentScratch.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
