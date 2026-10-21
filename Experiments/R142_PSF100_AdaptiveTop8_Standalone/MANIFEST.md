# R142_PSF100_AdaptiveTop8_Standalone 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

擴為100顆並逐張選八顆

指定實測100顆未安裝；推論拒絕是正確行為，合成測試不冒充實測

## 必要來源

未訓練起點、安裝條件與缺件紀錄，不能放測試PSF充數

## 影像保存

機制受控測試與缺少真實來源的狀態

## 原始報告

- [MODEL_CARD.md](MODEL_CARD.md)
- [PACKAGING_CHANGELOG.md](PACKAGING_CHANGELOG.md)
- [README.md](README.md)
- [BANK_REQUIRED.md](calibration/BANK_REQUIRED.md)
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

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R142_PSF100_AdaptiveTop8_Standalone.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
