# R104_PhotometricInvariantCausalGateScratch 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

將形狀判斷與絕對亮度分離

設計中的幾何頭未直接形成最終邊界，需由後續R105驗證

## 必要來源

程序成像與相對亮度設定、各分支實際結果

## 影像保存

亮度不變形控制、邊界與必要性閘

## 原始報告

- [README.md](README.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [analysis/analyze_model_internals.py](analysis/analyze_model_internals.py)
- [analysis/evaluate_checkpoint_candidates.py](analysis/evaluate_checkpoint_candidates.py)
- [analysis/run_adapted_validation.py](analysis/run_adapted_validation.py)
- [inference/reconstruct.py](inference/reconstruct.py)
- [model/r104_model.py](model/r104_model.py)
- [scripts/monitor_training.ps1](scripts/monitor_training.ps1)
- [scripts/start_formal_training.ps1](scripts/start_formal_training.ps1)
- [tests/autotune_batch.py](tests/autotune_batch.py)
- [tests/formal_runtime_preflight.py](tests/formal_runtime_preflight.py)
- [tests/micro_overfit.py](tests/micro_overfit.py)
- [tests/preflight.py](tests/preflight.py)
- [training/losses.py](training/losses.py)
- [training/r104_dataset.py](training/r104_dataset.py)
- [training/run_full_training.py](training/run_full_training.py)
- [training/train_r104.py](training/train_r104.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R104_PhotometricInvariantCausalGateScratch.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
