# R108C_IndependentOpticalSpecialistsMicroprobe 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

分開檢查邊緣、紋理、去噪與照明專家

任一專家未通過就不訓練組合，保留停止原因

## 必要來源

R108B資料的精確引用及四個獨立初值

## 影像保存

各專家本身的收益與失敗

## 原始報告

- [README.md](README.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [scripts/analyze_5x_edge_alignment.py](scripts/analyze_5x_edge_alignment.py)
- [scripts/analyze_r79_sem_action_basis.py](scripts/analyze_r79_sem_action_basis.py)
- [scripts/analyze_sem_stage_ablation.py](scripts/analyze_sem_stage_ablation.py)
- [scripts/calibrate_denoise_adoption.py](scripts/calibrate_denoise_adoption.py)
- [scripts/evaluate_no_radiometry.py](scripts/evaluate_no_radiometry.py)
- [scripts/evaluate_real_motion.py](scripts/evaluate_real_motion.py)
- [scripts/infer_calibrated.py](scripts/infer_calibrated.py)
- [scripts/infer_no_radiometry_folder.py](scripts/infer_no_radiometry_folder.py)
- [scripts/infer_sem_stage_ablation.py](scripts/infer_sem_stage_ablation.py)
- [scripts/infer_stage_ablation.py](scripts/infer_stage_ablation.py)
- [scripts/prepare_acm_runs.py](scripts/prepare_acm_runs.py)
- [scripts/prepare_direct_probe_acm.py](scripts/prepare_direct_probe_acm.py)
- [scripts/prepare_no_radiometry_acm.py](scripts/prepare_no_radiometry_acm.py)
- [scripts/prepare_stage_acm.py](scripts/prepare_stage_acm.py)
- [scripts/probe_direct_edge_texture.py](scripts/probe_direct_edge_texture.py)
- [scripts/run_specialists.py](scripts/run_specialists.py)
- [scripts/train_adoptions.py](scripts/train_adoptions.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R108C_IndependentOpticalSpecialistsMicroprobe.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
