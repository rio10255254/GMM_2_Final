# R151_R148v2_AdaptivePSFFusion 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

恢復可參與學習的光學加權融合

機制可運作但現有25顆不能可靠辨識，未開始正式8192

## 必要來源

精確25PSF、選擇可辨識前測、受限殘差與短測模型

## 影像保存

可區分控制、現有PSF失敗及原尺寸實拍

## 原始報告

- [R151_DESIGN_AND_PREFLIGHT.md](reports/R151_DESIGN_AND_PREFLIGHT.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [dataset.py](dataset.py)
- [losses.py](losses.py)
- [model.py](model.py)
- [optical/adaptive_fourier_psf.py](optical/adaptive_fourier_psf.py)
- [optical/fullres_psf.py](optical/fullres_psf.py)
- [scripts/preflight.py](scripts/preflight.py)
- [scripts/probe_basis_selector.py](scripts/probe_basis_selector.py)
- [scripts/probe_context_selector.py](scripts/probe_context_selector.py)
- [scripts/probe_descriptor_selector.py](scripts/probe_descriptor_selector.py)
- [scripts/probe_matched_selector_pretrain.py](scripts/probe_matched_selector_pretrain.py)
- [scripts/probe_selector.py](scripts/probe_selector.py)
- [scripts/smoke_real_frame.py](scripts/smoke_real_frame.py)
- [scripts/verify_package.py](scripts/verify_package.py)
- [train.py](train.py)
- [training_policy.py](training_policy.py)
- [utils.py](utils.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R151_R148v2_AdaptivePSFFusion.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
