# R101_HighFrequencyCausalAblation 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

相同起點逐步加入弱邊緣及連續邊界機制

A／B／C為短期機制驗證，不能冒充正式長訓練模型

## 必要來源

共同生成場景、共同初值與各組完整數值

## 影像保存

相同圖像下三組邊界中心／細節差異

## 原始報告

- [EXPERIMENT_RESULTS.md](EXPERIMENT_RESULTS.md)
- [README.md](README.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [analysis/diagnose_mechanisms.py](analysis/diagnose_mechanisms.py)
- [data/generate_continuous_dataset.py](data/generate_continuous_dataset.py)
- [evaluation/evaluate_repair_ablation.py](evaluation/evaluate_repair_ablation.py)
- [evaluation/evaluate_short_ablation.py](evaluation/evaluate_short_ablation.py)
- [model/prototype_models.py](model/prototype_models.py)
- [model/repaired_models.py](model/repaired_models.py)
- [scripts/run_all.ps1](scripts/run_all.ps1)
- [training/run_repair_ablation.py](training/run_repair_ablation.py)
- [training/run_short_ablation.py](training/run_short_ablation.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R101_HighFrequencyCausalAblation.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
