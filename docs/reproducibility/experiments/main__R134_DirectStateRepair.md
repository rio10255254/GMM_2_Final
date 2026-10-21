# main/R134_DirectStateRepair 研究與重做紀錄

直接修正影像狀態並避免8bit存檔誤導

精度修正版長訓練與最後比較完成；舊8bit失敗仍保留，尚未正式採用

## 必要來源

P1精確模型、保存精度、兩起點短測及長訓練資料

## 影像保存理由

8bit／保留精度、橫向偏移與SEM得失

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

- [原始報告：R134 校準與資料准入現況](<../../../Experiments/R134_DirectStateRepair/reports/R134_CALIBRATION_STATUS.md>)
- [原始報告：R134：第16至17張側向偏移的原因](<../../../Experiments/R134_DirectStateRepair/reports/R134_CROSS_AXIS_DIAGNOSIS.md>)
- [原始報告：每代長訓練模型的獨立套件要求](<../../../Experiments/R134_DirectStateRepair/reports/R134_LONG_PACKAGE_SPEC.md>)
- [原始報告：R134 固定短測方法](<../../../Experiments/R134_DirectStateRepair/reports/R134_METHODOLOGY.md>)
- [原始報告：R134 P1：保留量測精度的完整驗證與訓練](<../../../Experiments/R134_DirectStateRepair/reports/R134_PRECISION_REVALIDATION.md>)
- [原始報告：R134 執行結果與目前狀態](<../../../Experiments/R134_DirectStateRepair/reports/R134_RESULTS.md>)

## 重做與驗證範圍

程式、設定、完整表格與選定影像依保存清單收錄；大型必要來源和固定模型由附件恢復。
本次沒有重跑這一輪全部歷史訓練。可攜執行、完整數值重算與來源逐份核對的實測範圍，請看總入口的驗證紀錄。
任何仍須讀取僅存在D／H原工作區的檔案，都不能列為僅靠GitHub已完整重現。

## 2026年10月16日保存核對

本輪入選的方法、設定、完整數值與代表影像已完成逐份內容核對並保存到GitHub；共用來源與先前移到H槽的歷史版本，按總入口的附件索引取回。

本次完成保存與完整檔案內容核對，沒有重跑本輪全部歷史訓練；原成功、失敗、中止及限制照原報告保留。

D槽副本移除遭執行工具拒絕，本輪沒有因這次整理而被清理。
