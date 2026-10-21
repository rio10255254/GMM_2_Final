# R122_OperatorPrinciples 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

驗證位置／寬度操作與V42訓練來源

插值不保證獨立操作；V42評估來源重用訓練，不能稱未知驗證

## 必要來源

7776操作、360成像控制、實際V42訓練／分組清單

## 影像保存

位置寬度耦合與資料祖源對照

## 原始報告

- [MODEL_DESIGN.md](reports/MODEL_DESIGN.md)
- [R122_RESULTS.md](reports/R122_RESULTS.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [scripts/audit_provenance.py](scripts/audit_provenance.py)
- [scripts/audit_provenance_v1_failed.py](scripts/audit_provenance_v1_failed.py)
- [scripts/extend_provenance.py](scripts/extend_provenance.py)
- [scripts/final_check.py](scripts/final_check.py)
- [scripts/independent_qa.py](scripts/independent_qa.py)
- [scripts/physical_fit_area.py](scripts/physical_fit_area.py)
- [scripts/split_guard.py](scripts/split_guard.py)
- [scripts/verify_operators.py](scripts/verify_operators.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R122_OperatorPrinciples.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
