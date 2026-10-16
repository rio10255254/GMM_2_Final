# R108G_MidpointWidthFactorizedProfileMicroprobe 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

將法線位移與保中點寬度修正分開

此短測成為R109依據，仍不等於完整模型驗收

## 必要來源

精確R108E資料、先偵測後渲染設定

## 影像保存

中點／寬度分工及不修改案例

## 原始報告

- [README.md](README.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [scripts/evaluate_real_motion.py](scripts/evaluate_real_motion.py)
- [scripts/infer_external_parameter_smoothing.py](scripts/infer_external_parameter_smoothing.py)
- [scripts/infer_locked_suites.py](scripts/infer_locked_suites.py)
- [scripts/infer_sem_parameter_smoothing.py](scripts/infer_sem_parameter_smoothing.py)
- [scripts/prepare_acm.py](scripts/prepare_acm.py)
- [scripts/prepare_smooth_acm.py](scripts/prepare_smooth_acm.py)
- [scripts/run_probe.py](scripts/run_probe.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R108G_MidpointWidthFactorizedProfileMicroprobe.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
