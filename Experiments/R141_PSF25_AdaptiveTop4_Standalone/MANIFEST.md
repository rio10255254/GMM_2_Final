# R141_PSF25_AdaptiveTop4_Standalone 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

逐張從25顆光學候選選四顆

衍生自R140v2的可推論包，非已完成新長訓練與930驗收

## 必要來源

精確衍生模型、25PSF及逐影像標記需求

## 影像保存

接線／選擇受控測試與單張實拍差異

## 原始報告

- [MODEL_CARD.md](MODEL_CARD.md)
- [PACKAGING_CHANGELOG.md](PACKAGING_CHANGELOG.md)
- [README.md](README.md)
- [PACKAGE_VALIDATION.md](results/PACKAGE_VALIDATION.md)
- [VALIDATION.md](tests/VALIDATION.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [dataset.py](dataset.py)
- [derive_weights.py](derive_weights.py)
- [evaluation/__init__.py](evaluation/__init__.py)
- [evaluation/measurement_interface.py](evaluation/measurement_interface.py)
- [evaluation/reference_circle_core.py](evaluation/reference_circle_core.py)
- [infer.py](infer.py)
- [install_bank.py](install_bank.py)
- [losses.py](losses.py)
- [model.py](model.py)
- [optical/__init__.py](optical/__init__.py)
- [optical/adaptive_psf.py](optical/adaptive_psf.py)
- [tests/integration_full_model.py](tests/integration_full_model.py)
- [tests/probe_external_labeled_data.py](tests/probe_external_labeled_data.py)
- [tests/probe_physical_selection.py](tests/probe_physical_selection.py)
- [tests/probe_selector.py](tests/probe_selector.py)
- [train.py](train.py)
- [training_policy.py](training_policy.py)
- [utils.py](utils.py)
- [verify_package.py](verify_package.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R141_PSF25_AdaptiveTop4_Standalone.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
