# R112_V42R109GMFMechanismDecomposition 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

拆解V42與R109外部GMF差異

內部模板沒有重現外部排序，因此未用來挑反事實架構

## 必要來源

同100座標／99步、原外部分數與固定模型

## 影像保存

低頻錨定、局部寬度／位移及被否決代理

## 原始報告

- [MODEL_IMPROVEMENT_DESIGN.md](MODEL_IMPROVEMENT_DESIGN.md)
- [README.md](README.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [scripts/analyze_counterfactual_stability.py](scripts/analyze_counterfactual_stability.py)
- [scripts/analyze_image_mechanisms.py](scripts/analyze_image_mechanisms.py)
- [scripts/analyze_residual_bands.py](scripts/analyze_residual_bands.py)
- [scripts/probe_internal_dynamics.py](scripts/probe_internal_dynamics.py)
- [scripts/probe_model_components.py](scripts/probe_model_components.py)
- [scripts/synthesize_findings.py](scripts/synthesize_findings.py)
- [scripts/validate_r112.py](scripts/validate_r112.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R112_V42R109GMFMechanismDecomposition.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
