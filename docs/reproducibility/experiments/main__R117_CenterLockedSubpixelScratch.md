# main/R117_CenterLockedSubpixelScratch 研究與重做紀錄

保留必要法線位移並避免寬度造成額外中心移動

來源是8倍生成後積分，不用實體答案或舊權重

## 必要來源

本輪生成、被固定的成像形成順序及正式模型

## 影像保存理由

中心與寬度互相影響的控制及實體失敗

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

- [MANIFEST.md](../../../Experiments/R117_CenterLockedSubpixelScratch/MANIFEST.md)
- [README.md](../../../Experiments/R117_CenterLockedSubpixelScratch/README.md)
- [FINDINGS.md](../../../Experiments/R117_CenterLockedSubpixelScratch/analysis/design_audit_20260905/FINDINGS.md)

## 重做與驗證範圍

程式、設定、完整表格與選定影像依保存清單收錄；大型必要來源和固定模型由附件恢復。
本次沒有重跑這一輪全部歷史訓練。可攜執行、完整數值重算與來源逐份核對的實測範圍，請看總入口的驗證紀錄。
任何仍須讀取僅存在D／H原工作區的檔案，都不能列為僅靠GitHub已完整重現。
