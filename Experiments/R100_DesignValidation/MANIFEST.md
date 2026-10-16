# R100_DesignValidation 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

訓練前檢查幾何零點、細節及量測讀法

這是分析前測，沒有R100正式模型

## 必要來源

固定程序控制、既有真實來源及原始讀值

## 影像保存

改亮暗但幾何不變的量測敏感度

## 原始報告

- [README.md](README.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [analysis/run_acm_photometric_audit.m](analysis/run_acm_photometric_audit.m)
- [analysis/run_architecture_falsification.py](analysis/run_architecture_falsification.py)
- [analysis/run_core_validation.py](analysis/run_core_validation.py)
- [analysis/summarize_validation.py](analysis/summarize_validation.py)
- [scripts/Run_Validation.ps1](scripts/Run_Validation.ps1)
- [tests/test_validation_artifacts.py](tests/test_validation_artifacts.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R100_DesignValidation.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
