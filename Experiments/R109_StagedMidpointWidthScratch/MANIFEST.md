# R109_StagedMidpointWidthScratch 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

先固定偵測，再學受限位移與單調寬度

48輪研究模型，後來LSC與外部GMF判讀不同；保留全部量法

## 必要來源

5000／512程序資料、兩階段設定及E48模型

## 影像保存

中點、寬度、實體輪廓及外部穩定性

## 原始報告

- [R108C_TO_R109_DECISION_CHAIN_ZH.md](reports/R108C_TO_R109_DECISION_CHAIN_ZH.md)
- [R109_FINAL_SELECTION_ZH.md](reports/R109_FINAL_SELECTION_ZH.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [data/prepare_dataset.py](data/prepare_dataset.py)
- [inference/run_folder.py](inference/run_folder.py)
- [model/r109_model.py](model/r109_model.py)
- [requirements.txt](requirements.txt)
- [scripts/finalize_preparation.py](scripts/finalize_preparation.py)
- [scripts/finalize_r109.py](scripts/finalize_r109.py)
- [scripts/infer.ps1](scripts/infer.ps1)
- [scripts/monitor_training.ps1](scripts/monitor_training.ps1)
- [scripts/prepare_data.ps1](scripts/prepare_data.ps1)
- [scripts/smoke_test.ps1](scripts/smoke_test.ps1)
- [scripts/start_formal_training.ps1](scripts/start_formal_training.ps1)
- [scripts/train.ps1](scripts/train.ps1)
- [scripts/validate.ps1](scripts/validate.ps1)
- [training/losses.py](training/losses.py)
- [training/r109_dataset.py](training/r109_dataset.py)
- [training/train.py](training/train.py)
- [validation/analyze_need_probe.py](validation/analyze_need_probe.py)
- [validation/evaluate_real_motion.py](validation/evaluate_real_motion.py)
- [validation/prepare_acm.py](validation/prepare_acm.py)
- [validation/reconstruct_locked_suites.py](validation/reconstruct_locked_suites.py)
- [validation/validate_prepared.py](validation/validate_prepared.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R109_StagedMidpointWidthScratch.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
