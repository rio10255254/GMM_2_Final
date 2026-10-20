# main/R94_EvidenceConditionalScratch 研究與重做紀錄

按成像順序分工並直接教何時需要修正

第8輪失敗後結案；失敗紀錄是R95修復依據

## 必要來源

R93鎖定資料、初值與第8輪錯誤／梯度診斷

## 影像保存理由

接近原圖的輸出與未生效修正

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

- [原始報告：R94 Manifest](<../../../Experiments/R94_EvidenceConditionalScratch/MANIFEST.md>)
- [原始報告：R94 Evidence-Conditional Scratch](<../../../Experiments/R94_EvidenceConditionalScratch/README.md>)
- [原始報告：R94 data policy](<../../../Experiments/R94_EvidenceConditionalScratch/data/README.md>)
- [原始報告：R94 weights](<../../../Experiments/R94_EvidenceConditionalScratch/weights/README.md>)

## 重做與驗證範圍

程式、設定、完整表格與選定影像依保存清單收錄；大型必要來源和固定模型由附件恢復。
本次沒有重跑這一輪全部歷史訓練。可攜執行、完整數值重算與來源逐份核對的實測範圍，請看總入口的驗證紀錄。
任何仍須讀取僅存在D／H原工作區的檔案，都不能列為僅靠GitHub已完整重現。

## 2026年10月16日保存核對

本輪入選的方法、設定、完整數值與代表影像已完成逐份內容核對並保存到GitHub；共用來源與先前移到H槽的歷史版本，按總入口的附件索引取回。

本次完成保存與完整檔案內容核對，沒有重跑本輪全部歷史訓練；原成功、失敗、中止及限制照原報告保留。

D槽副本移除遭執行工具拒絕，本輪沒有因這次整理而被清理。


## 2026年10月20日 GitHub 共用來源重做核對

R93 固定來源已從 GitHub 完整取回，15,004 檔逐份相同。本輪原讀取程式在新 CPU 環境、新位置實際讀取八種用途及首／中／尾，與原工作區準備的內容比較；五輪合計45個代表樣本。這證明本輪共享輸入鏈可在舊資料不可讀時使用，不代表重新完成本輪歷史訓練。R94第8輪失敗等原狀態仍保留。

[取得方式與實測範圍](../r93_shared/README.md)／[核對收據](../r93_shared/VERIFICATION_20261020.json)。

## 2026年10月21日 完整歷程與原模型取回

完整8輪；第9輪未提交即停止，所有原失敗與空啟動保留。所有現存模型、原表、影像與失敗紀錄完整保存；本輪兩個正式端點×四個固定實拍輸入的8組原推論，從GitHub取回後在新CPU環境重做，完整輸出與原程式CPU參照相同。舊D／H研究位置不可讀、四輪共用輸入及數字小包重算也通過。沒有清理D、沒有重跑歷史訓練；較早程式版本缺件明列。

[本輪完整審查](../../../Experiments/R94_EvidenceConditionalScratch/reports/R94_AUDIT.md)／[取得方法與收據](../four_rounds/README.md)。
