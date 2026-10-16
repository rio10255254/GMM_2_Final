# R103_RecoverableDetailScratch 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

修復不可知亮暗答案與正規化造成的細節流失

來源／答案共用曝光，低頻／輪廓／紋理分工；保留曝光轉折失敗

## 必要來源

程序配方、清楚反例與固定損失設定

## 影像保存

曝光18前後、紋理收益和清楚影像代價

## 原始報告

- [README.md](README.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [Open_Training_Monitor.cmd](Open_Training_Monitor.cmd)
- [Start_R103_Training.cmd](Start_R103_Training.cmd)
- [analysis/analyze_model_internals.py](analysis/analyze_model_internals.py)
- [analysis/evaluate_checkpoint_candidates.py](analysis/evaluate_checkpoint_candidates.py)
- [analysis/evaluate_external_acm.py](analysis/evaluate_external_acm.py)
- [analysis/evaluate_large_frame_tile_parity.py](analysis/evaluate_large_frame_tile_parity.py)
- [analysis/evaluate_real_sequences.py](analysis/evaluate_real_sequences.py)
- [analysis/evaluate_sem_contour.py](analysis/evaluate_sem_contour.py)
- [analysis/run_causal_alpha_probe.py](analysis/run_causal_alpha_probe.py)
- [analysis/summarize_alpha_headroom.py](analysis/summarize_alpha_headroom.py)
- [analysis/summarize_posttraining_validation.py](analysis/summarize_posttraining_validation.py)
- [data/prepare_data.py](data/prepare_data.py)
- [evaluation/validate.py](evaluation/validate.py)
- [inference/reconstruct.py](inference/reconstruct.py)
- [inference/run_inference.py](inference/run_inference.py)
- [model/r103_model.py](model/r103_model.py)
- [scripts/monitor_training.ps1](scripts/monitor_training.ps1)
- [scripts/start_formal_training.ps1](scripts/start_formal_training.ps1)
- [tests/preflight.py](tests/preflight.py)
- [training/losses.py](training/losses.py)
- [training/r103_dataset.py](training/r103_dataset.py)
- [training/run_full_training.py](training/run_full_training.py)
- [training/train_r103.py](training/train_r103.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R103_RecoverableDetailScratch.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
