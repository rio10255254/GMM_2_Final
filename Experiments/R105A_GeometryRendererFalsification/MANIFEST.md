# R105A_GeometryRendererFalsification 研究保存清單

清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。

## 研究問題與判讀

以學到的幾何直接畫出最終邊界

1800次對照改善寬度但傷中心、形狀及切片；不開正式R105

## 必要來源

共同初值、4倍幾何、600／1800次及原低解析失敗

## 影像保存

變窄卻移位、光暈與切片失敗

## 原始報告

- [R105A_RESULTS.md](archive/pilot_lowres_sdf_20260824/reports/R105A_RESULTS.md)
- [R105A_RESULTS.md](archive/supersampled_0600step_20260824/reports/R105A_RESULTS.md)
- [R105A_BLEND_SWEEP.md](reports/R105A_BLEND_SWEEP.md)
- [R105A_FINAL_FINDINGS_ZH.md](reports/R105A_FINAL_FINDINGS_ZH.md)
- [R105A_RESULTS.md](reports/R105A_RESULTS.md)

## 程式查找

以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。

- [scripts/analyze_internal_geometry.py](scripts/analyze_internal_geometry.py)
- [scripts/render_qa.py](scripts/render_qa.py)
- [scripts/run_all.py](scripts/run_all.py)
- [scripts/sweep_renderer_blend.py](scripts/sweep_renderer_blend.py)

## 保存與重做範圍

[逐輪完整判讀](../../docs/reproducibility/experiments/main__R105A_GeometryRendererFalsification.md)。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。
D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。
