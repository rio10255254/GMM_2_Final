# main/R95_CounterfactualGateRepairScratch 研究與重做紀錄

[直接查看這一輪的檔案分工](<../../../Experiments/R95_CounterfactualGateRepairScratch/FILE_GUIDE.md>)

[全部實驗](../EXPERIMENTS.md) · [主R88至104：資料形成與可學性](../routes/main88_104.md) · [現在保存到哪裡](../STATUS.md)

本卡保留原研究與當次保存紀錄；較晚的來源補件及缺件請以[目前狀態](../STATUS.md)為準。已建立閱讀卡不代表這一輪的全部來源已查完。

修復R94修正閘與訓練動力問題

獨立48輪，不繼承R94權重；保留每分支的收益與後期退步

## 必要來源

R93資料、固定反事實設定及本輪完整48輪歷程

## 影像保存理由

各修正分支、清楚控制與後期紋理變化

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

- [原始報告：R95 Manifest](<../../../Experiments/R95_CounterfactualGateRepairScratch/MANIFEST.md>)
- [原始報告：R95 Evidence-Conditional Scratch](<../../../Experiments/R95_CounterfactualGateRepairScratch/README.md>)
- [原始報告：R95 data policy](<../../../Experiments/R95_CounterfactualGateRepairScratch/data/README.md>)

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

48輪完成；首度恢復重建更新狀態，49列原表及第9輪取代脈絡完整保留。所有現存模型、原表、影像與失敗紀錄完整保存；本輪兩個正式端點×四個固定實拍輸入的8組原推論，從GitHub取回後在新CPU環境重做，完整輸出與原程式CPU參照相同。舊D／H研究位置不可讀、四輪共用輸入及數字小包重算也通過。沒有清理D、沒有重跑歷史訓練；較早程式版本缺件明列。

[本輪完整審查](../../../Experiments/R95_CounterfactualGateRepairScratch/reports/R95_AUDIT.md)／[取得方法與收據](../four_rounds/README.md)。

## 2026年10月21日：補回兩版早期訓練程式

兩份原始程式已從本機舊保存物件找回，與當年登記內容完全相同，並實際從GitHub取回。較早版本沒有保存更新及隨機狀態，後一版本才加入，補強第一次第8輪回復時重建更新狀態的來源證據。此處沒有啟動訓練或更換最後版本；[原階段與差異](../../../Experiments/R95_CounterfactualGateRepairScratch/archive/recovered_training_sources_20261021/README.md)與[正式來源審查](../../../Experiments/R95_CounterfactualGateRepairScratch/reports/R95_AUDIT.md)保留其餘缺件界限。

## 資料生產方法與共用來源

[本輪原生產／讀取程式、設定與修正紀錄](../GENERATION_GUIDE.md)已按實際來源確認；基礎來源：r93。可再生的大檔不必上傳整套。原絕對位置與固定內容身分供歷史追查，日後在新的研究副本設定自己的來源位置；新生成內容與原件不同時須保留差異，不改寫舊結果。


---

[上一個閱讀入口：main/R94_EvidenceConditionalScratch](main__R94_EvidenceConditionalScratch.md) · [回本分區](../routes/main88_104.md) · [下一個閱讀入口：main/R96_Design_Archive](main__R96_Design_Archive.md)
