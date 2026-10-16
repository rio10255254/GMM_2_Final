# R108F_MonotonicProfileRendererMicroprobe 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

限制渲染範圍以避免暗圈與亮度超出

重用R108E資料但不用其模型；位移與寬度仍可能耦合

## 必要來源

R108E精確資料、兩階段全新模型及光學尺度設定

## 影像保存

暗圈消除與中心／寬度代價

## 原始報告

- [README.md](README.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [scripts/analyze_sem_signed_profiles.py](scripts/analyze_sem_signed_profiles.py)
- [scripts/infer_locked_suites.py](scripts/infer_locked_suites.py)
- [scripts/infer_sem_operator_ablation.py](scripts/infer_sem_operator_ablation.py)
- [scripts/prepare_acm.py](scripts/prepare_acm.py)
- [scripts/run_probe.py](scripts/run_probe.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R108F_MonotonicProfileRendererMicroprobe.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
