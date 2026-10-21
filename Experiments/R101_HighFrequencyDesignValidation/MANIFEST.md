# R101_HighFrequencyDesignValidation 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

檢查高頻機制的設計依據

與R101三組短訓練分開記錄，設計不算完成模型

## 必要來源

設計、既有測量及高頻診斷來源

## 影像保存

高頻與輪廓變化的控制圖

## 原始報告

- [R101_DESIGN.md](R101_DESIGN.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [scripts/analyze_r100_operator_trajectory.py](scripts/analyze_r100_operator_trajectory.py)
- [scripts/audit_boundary_supervision.py](scripts/audit_boundary_supervision.py)
- [scripts/audit_gradient_conflicts.py](scripts/audit_gradient_conflicts.py)
- [scripts/audit_r100_edge_support.py](scripts/audit_r100_edge_support.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R101_HighFrequencyDesignValidation.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
