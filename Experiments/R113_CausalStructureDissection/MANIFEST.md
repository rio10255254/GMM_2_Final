# R113_CausalStructureDissection 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

拆開渲染能力、學到控制、訓練軌跡與量法

已知答案上限、元件干預與檢查器修復分開保存

## 必要來源

V42／R61／R109固定模型、匹配來源及每個干預設定

## 影像保存

可達上限與實際模型、元件關閉及失敗

## 原始報告

- [MEASUREMENT_QA_FINDINGS.md](MEASUREMENT_QA_FINDINGS.md)
- [R113_FINDINGS_ZH.md](R113_FINDINGS_ZH.md)
- [README.md](README.md)
- [DEEP_AUDIT_FINDINGS_ZH.md](deep_audit/DEEP_AUDIT_FINDINGS_ZH.md)
- [R114_MASTER_PLAN_ZH.md](deep_audit/R114_MASTER_PLAN_ZH.md)
- [README.md](deep_audit/README.md)
- [DESIGN_DECISION.md](next_probe/DESIGN_DECISION.md)
- [README.md](next_probe/README.md)
- [FINDINGS.md](results/r109_expressivity/FINDINGS.md)
- [STRUCTURE_FINDINGS.md](results/structure/STRUCTURE_FINDINGS.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [deep_audit/scripts/analyze_training_contract.py](deep_audit/scripts/analyze_training_contract.py)
- [deep_audit/scripts/audit_clear_degraded_conflict.py](deep_audit/scripts/audit_clear_degraded_conflict.py)
- [deep_audit/scripts/audit_degradation_recoverability.py](deep_audit/scripts/audit_degradation_recoverability.py)
- [deep_audit/scripts/audit_domain_gap.py](deep_audit/scripts/audit_domain_gap.py)
- [deep_audit/scripts/audit_loss_gradients.py](deep_audit/scripts/audit_loss_gradients.py)
- [deep_audit/scripts/audit_model_internals.py](deep_audit/scripts/audit_model_internals.py)
- [deep_audit/scripts/build_notebook.py](deep_audit/scripts/build_notebook.py)
- [deep_audit/scripts/finalize_deep_audit.py](deep_audit/scripts/finalize_deep_audit.py)
- [deep_audit/scripts/probe_boundary_detectability.py](deep_audit/scripts/probe_boundary_detectability.py)
- [deep_audit/scripts/profile_training_data.py](deep_audit/scripts/profile_training_data.py)
- [deep_audit/scripts/validate_deep_audit.py](deep_audit/scripts/validate_deep_audit.py)
- [deep_audit/scripts/validate_r114_plan.py](deep_audit/scripts/validate_r114_plan.py)
- [next_probe/model/model.py](next_probe/model/model.py)
- [next_probe/scripts/check_supervision_capability.py](next_probe/scripts/check_supervision_capability.py)
- [next_probe/scripts/prepare_selection.py](next_probe/scripts/prepare_selection.py)
- [next_probe/scripts/run_formal.ps1](next_probe/scripts/run_formal.ps1)
- [next_probe/scripts/run_probe.py](next_probe/scripts/run_probe.py)
- [next_probe/scripts/run_smoke.ps1](next_probe/scripts/run_smoke.ps1)
- [next_probe/scripts/run_supervised_smoke.ps1](next_probe/scripts/run_supervised_smoke.ps1)
- [next_probe/scripts/validate_formal_probe.py](next_probe/scripts/validate_formal_probe.py)
- [next_probe/scripts/validate_probe.py](next_probe/scripts/validate_probe.py)
- [next_probe/scripts/validate_supervised_formal.py](next_probe/scripts/validate_supervised_formal.py)
- [next_probe/scripts/validate_supervised_smoke.py](next_probe/scripts/validate_supervised_smoke.py)
- [next_probe/tests/test_contracts.py](next_probe/tests/test_contracts.py)
- [next_probe/training/dataset.py](next_probe/training/dataset.py)
- [next_probe/training/losses.py](next_probe/training/losses.py)
- [next_probe/training/supervision.py](next_probe/training/supervision.py)
- [scripts/analyze_lsc_interventions.py](scripts/analyze_lsc_interventions.py)
- [scripts/analyze_sem_intervention_uncertainty.py](scripts/analyze_sem_intervention_uncertainty.py)
- [scripts/analyze_synthetic_intervention_uncertainty.py](scripts/analyze_synthetic_intervention_uncertainty.py)
- [scripts/build_analysis_notebook.py](scripts/build_analysis_notebook.py)
- [scripts/finalize_r113.py](scripts/finalize_r113.py)
- [scripts/generate_lsc_interventions.py](scripts/generate_lsc_interventions.py)
- [scripts/generate_r109_intervention_suites.py](scripts/generate_r109_intervention_suites.py)
- [scripts/measurement_qa/compare_r112_measurements.py](scripts/measurement_qa/compare_r112_measurements.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R113_CausalStructureDissection.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
