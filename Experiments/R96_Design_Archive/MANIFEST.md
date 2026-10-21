# R96_Design_Archive 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

保存R96正式設計前的方案

設計歷史不等於正式訓練結果

## 必要來源

被取代方案、差異及轉向原因

## 影像保存

只保留能解釋設計取捨的示意與對照

## 原始報告


## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [scripts/analyze_branch_interventions.py](scripts/analyze_branch_interventions.py)
- [scripts/analyze_model_internals.py](scripts/analyze_model_internals.py)
- [scripts/analyze_r93_reuse.py](scripts/analyze_r93_reuse.py)
- [scripts/audit_auxiliary_gradient_conflicts.py](scripts/audit_auxiliary_gradient_conflicts.py)
- [scripts/audit_full_branch_gradient_conflicts.py](scripts/audit_full_branch_gradient_conflicts.py)
- [scripts/audit_objective_gradient_conflicts.py](scripts/audit_objective_gradient_conflicts.py)
- [scripts/audit_sparse_branch_supervision.py](scripts/audit_sparse_branch_supervision.py)
- [scripts/formal_internal_audit.py](scripts/formal_internal_audit.py)
- [scripts/prepare_epoch32_memory_recovery.py](scripts/prepare_epoch32_memory_recovery.py)
- [scripts/summarize_internal_analysis.py](scripts/summarize_internal_analysis.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R96_Design_Archive.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
