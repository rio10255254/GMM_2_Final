# main/R97_DirectCausalPhaseScratch 研究與重做紀錄

[直接查看這一輪的檔案分工](<../../../Experiments/R97_DirectCausalPhaseScratch/FILE_GUIDE.md>)

[全部實驗](../EXPERIMENTS.md) · [主R88至104：資料形成與可學性](../routes/main88_104.md) · [現在保存到哪裡](../STATUS.md)

本卡保留原研究與當次保存紀錄；較晚的來源補件及缺件請以[目前狀態](../STATUS.md)為準。已建立閱讀卡不代表這一輪的全部來源已查完。

直接預測每分支實際施加的修正

移除壓制有效修正的振幅閘；從零訓練且需保留週期誤配問題

## 必要來源

R93資料、線上程序週期樣本、48輪設定

## 影像保存理由

週期錯峰、細節與修正抵消

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

- [原始報告：GPU incident record — 2026-08-13](<../../../Experiments/R97_DirectCausalPhaseScratch/reports/gpu_incident_20260813.md>)
- [原始報告：Same-run interruption recovery validation — 2026-08-13](<../../../Experiments/R97_DirectCausalPhaseScratch/reports/recovery_validation_20260813.md>)
- [原始報告：R97 root-cause matrix](<../../../Experiments/R97_DirectCausalPhaseScratch/reports/root_cause_matrix.md>)

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

48輪完成；固定48輪後測、兩種事故及細節／量測限制分別保存。所有現存模型、原表、影像與失敗紀錄完整保存；本輪兩個正式端點×四個固定實拍輸入的8組原推論，從GitHub取回後在新CPU環境重做，完整輸出與原程式CPU參照相同。舊D／H研究位置不可讀、四輪共用輸入及數字小包重算也通過。沒有清理D、沒有重跑歷史訓練；較早程式版本缺件明列。

[本輪完整審查](../../../Experiments/R97_DirectCausalPhaseScratch/reports/R97_AUDIT.md)／[取得方法與收據](../four_rounds/README.md)。

## 資料生產方法與共用來源

[本輪原生產／讀取程式、設定與修正紀錄](../GENERATION_GUIDE.md)已按實際來源確認；基礎來源：r93。可再生的大檔不必上傳整套。原絕對位置與固定內容身分供歷史追查，日後在新的研究副本設定自己的來源位置；新生成內容與原件不同時須保留差異，不改寫舊結果。


---

[上一個閱讀入口：main/R96_LocalizedEvidenceProtectedScratch](main__R96_LocalizedEvidenceProtectedScratch.md) · [回本分區](../routes/main88_104.md) · [下一個閱讀入口：main/R98_AggressiveTextureScratch](main__R98_AggressiveTextureScratch.md)
