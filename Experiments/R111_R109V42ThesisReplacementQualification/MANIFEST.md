# R111_R109V42ThesisReplacementQualification 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

判斷R109能否替換論文V42

固定LSC相近但外部GMF較弱；保留量測器狀態修復與不能全面替換結論

## 必要來源

V42 E120、R109 E48、Raw固定名單、重設後的量測程式

## 影像保存

不同目標的優劣與反覆量測一致性

## 原始報告

- [README.md](README.md)
- [UNIFIED_AUDIT_REPORT_TW.md](results/thesis_displacement_r109/UNIFIED_AUDIT_REPORT_TW.md)
- [CANDIDATE_READOUT_TW.md](results/thesis_displacement_r109/candidate/CANDIDATE_READOUT_TW.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [scripts/analyze_lsc_current_top30.py](scripts/analyze_lsc_current_top30.py)
- [scripts/analyze_three_way_gmf.py](scripts/analyze_three_way_gmf.py)
- [scripts/build_v42_external_gmf.py](scripts/build_v42_external_gmf.py)
- [scripts/finalize_policy_v2.py](scripts/finalize_policy_v2.py)
- [scripts/finalize_policy_v3_lsc.py](scripts/finalize_policy_v3_lsc.py)
- [scripts/finalize_qualification.py](scripts/finalize_qualification.py)
- [scripts/run_current_top30_lsc_comparison.py](scripts/run_current_top30_lsc_comparison.py)
- [scripts/run_local_qualification.py](scripts/run_local_qualification.py)
- [scripts/run_r109_lsc_displacement.py](scripts/run_r109_lsc_displacement.py)
- [scripts/validate_r111.py](scripts/validate_r111.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R111_R109V42ThesisReplacementQualification.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
