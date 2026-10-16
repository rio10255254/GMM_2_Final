# R115_R109DecoupledNormalProfileScratch 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

以獨立法線證據決定R109動作採用量

原資料與240張替換版分開；探針載舊模型不等於正式繼承

## 必要來源

A／B兩版精確資料、短探針和正式身分記錄

## 影像保存

採用量、替換前後及未過門檻

## 原始報告

- [R115_DESIGN_AND_PROBE_ZH.md](reports/R115_DESIGN_AND_PROBE_ZH.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [data/prepare_dataset.py](data/prepare_dataset.py)
- [inference/tiled.py](inference/tiled.py)
- [model/__init__.py](model/__init__.py)
- [model/r115_model.py](model/r115_model.py)
- [probes/run_ablation_probe.py](probes/run_ablation_probe.py)
- [scripts/monitor_training.ps1](scripts/monitor_training.ps1)
- [scripts/prepare_data.ps1](scripts/prepare_data.ps1)
- [scripts/run_ablation_probe.ps1](scripts/run_ablation_probe.ps1)
- [scripts/smoke_test.ps1](scripts/smoke_test.ps1)
- [scripts/train.ps1](scripts/train.ps1)
- [scripts/validate.ps1](scripts/validate.ps1)
- [tests/test_data.py](tests/test_data.py)
- [tests/test_losses.py](tests/test_losses.py)
- [tests/test_model.py](tests/test_model.py)
- [training/losses.py](training/losses.py)
- [training/r115_dataset.py](training/r115_dataset.py)
- [training/train.py](training/train.py)
- [validation/adapter.py](validation/adapter.py)
- [validation/run_locked_acm.py](validation/run_locked_acm.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R115_R109DecoupledNormalProfileScratch.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
