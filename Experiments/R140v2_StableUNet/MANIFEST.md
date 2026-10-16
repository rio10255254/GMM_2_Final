# R140v2_StableUNet 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

獨立重新封裝穩定U-Net

8192與930完成，光學仍等權；短步收益與尺寸限制分開

## 必要來源

凍結程式、最後模型、PSF與R130來源

## 影像保存

位移、光學權重歷程與尺寸比較

## 原始報告

- [R140v2_CAUSAL_REPAIR.md](reports/R140v2_CAUSAL_REPAIR.md)
- [R140v2_PSF_GATE_CAUSAL_AUDIT.md](reports/R140v2_PSF_GATE_CAUSAL_AUDIT.md)
- [R140v2_RESULTS.md](reports/R140v2_RESULTS.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [compare_measurements.py](compare_measurements.py)
- [dataset.py](dataset.py)
- [evaluate_real_measurement.py](evaluate_real_measurement.py)
- [evaluation/__init__.py](evaluation/__init__.py)
- [evaluation/measurement_interface.py](evaluation/measurement_interface.py)
- [evaluation/reference_circle_core.py](evaluation/reference_circle_core.py)
- [final_audit.py](final_audit.py)
- [formal/closeout.py](formal/closeout.py)
- [formal/launch.py](formal/launch.py)
- [formal/monitor.py](formal/monitor.py)
- [formal/preflight.py](formal/preflight.py)
- [formal/train.py](formal/train.py)
- [infer_model.py](infer_model.py)
- [losses.py](losses.py)
- [model.py](model.py)
- [optical/__init__.py](optical/__init__.py)
- [optical/feature.py](optical/feature.py)
- [reports/_docbuild/build_full_report.py](reports/_docbuild/build_full_report.py)
- [reports/_docbuild/diagnose_psf_gate.py](reports/_docbuild/diagnose_psf_gate.py)
- [reports/_docbuild/diagnose_psf_real.py](reports/_docbuild/diagnose_psf_real.py)
- [reports/_docbuild/prepare_document_assets.py](reports/_docbuild/prepare_document_assets.py)
- [scripts/full_size_preflight.py](scripts/full_size_preflight.py)
- [scripts/pilot.py](scripts/pilot.py)
- [training_policy.py](training_policy.py)
- [utils.py](utils.py)
- [write_report.py](write_report.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R140v2_StableUNet.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
