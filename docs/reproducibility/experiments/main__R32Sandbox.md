# main/R32Sandbox 研究與重做紀錄

加入真實影像訓練是否改善R30

內部檢查通過但外部0.8px大幅退步；保留未採用結論

## 必要來源

R30起始模型、真實訓練影像、固定合成資料與外部GMF原始回傳

## 影像保存理由

內外部結果落差及相同視野比較

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

- [ROUND32_DOMAIN_CAPACITY_AUDIT_0P8_SUMMARY_20260319_183506.md](../../../Experiments/R32Sandbox/reports/ROUND32_DOMAIN_CAPACITY_AUDIT_0P8_SUMMARY_20260319_183506.md)
- [ROUND32_DOMAIN_CAPACITY_AUDIT_0P8_r32_real_eq_finetune_20260319_183506.md](../../../Experiments/R32Sandbox/reports/ROUND32_DOMAIN_CAPACITY_AUDIT_0P8_r32_real_eq_finetune_20260319_183506.md)
- [ROUND32_DOMAIN_CAPACITY_AUDIT_8P0_SUMMARY_20260319_183546.md](../../../Experiments/R32Sandbox/reports/ROUND32_DOMAIN_CAPACITY_AUDIT_8P0_SUMMARY_20260319_183546.md)
- [ROUND32_DOMAIN_CAPACITY_AUDIT_8P0_r32_real_eq_finetune_20260319_183546.md](../../../Experiments/R32Sandbox/reports/ROUND32_DOMAIN_CAPACITY_AUDIT_8P0_r32_real_eq_finetune_20260319_183546.md)
- [ROUND32_DOMAIN_CAPACITY_DECISION_20260319_183614.md](../../../Experiments/R32Sandbox/reports/ROUND32_DOMAIN_CAPACITY_DECISION_20260319_183614.md)
- [ROUND32_DOMAIN_CAPACITY_SUMMARY_20260319_183506.md](../../../Experiments/R32Sandbox/reports/ROUND32_DOMAIN_CAPACITY_SUMMARY_20260319_183506.md)
- [ROUND32_EXTERNAL_COMPARE.md](../../../Experiments/R32Sandbox/reports/ROUND32_EXTERNAL_COMPARE.md)

## 重做與驗證範圍

程式、設定、完整表格與選定影像依保存清單收錄；大型必要來源和固定模型由附件恢復。
本次沒有重跑這一輪全部歷史訓練。可攜執行、完整數值重算與來源逐份核對的實測範圍，請看總入口的驗證紀錄。
任何仍須讀取僅存在D／H原工作區的檔案，都不能列為僅靠GitHub已完整重現。
