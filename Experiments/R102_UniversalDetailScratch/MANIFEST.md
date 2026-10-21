# R102_UniversalDetailScratch 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

以局部主幹同時恢復細節與位置

實際因原樣輸出塌縮而中止，原定48輪不算完成

## 必要來源

固定5000觀測、實際歷程與塌縮診斷

## 影像保存

看似穩定但沒有恢復的案例

## 原始報告

- [README.md](README.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [Open_Training_Monitor.cmd](Open_Training_Monitor.cmd)
- [Start_R102_Training.cmd](Start_R102_Training.cmd)
- [analysis/candidate_r103_model.py](analysis/candidate_r103_model.py)
- [analysis/deep_identity_collapse.py](analysis/deep_identity_collapse.py)
- [analysis/repair_ablation.py](analysis/repair_ablation.py)
- [analysis/truth_learning_probe.py](analysis/truth_learning_probe.py)
- [data/prepare_data.py](data/prepare_data.py)
- [evaluation/validate.py](evaluation/validate.py)
- [inference/reconstruct.py](inference/reconstruct.py)
- [inference/run_inference.py](inference/run_inference.py)
- [model/r102_model.py](model/r102_model.py)
- [scripts/monitor_training.ps1](scripts/monitor_training.ps1)
- [scripts/start_formal_training.ps1](scripts/start_formal_training.ps1)
- [tests/preflight.py](tests/preflight.py)
- [training/losses.py](training/losses.py)
- [training/r102_dataset.py](training/r102_dataset.py)
- [training/run_full_training.py](training/run_full_training.py)
- [training/train_r102.py](training/train_r102.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R102_UniversalDetailScratch.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
