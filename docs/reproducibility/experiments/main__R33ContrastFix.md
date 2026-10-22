# main/R33ContrastFix 研究與重做紀錄

[直接查看這一輪的檔案分工](<../../../Experiments/R33ContrastFix/FILE_GUIDE.md>)

[全部實驗](../EXPERIMENTS.md) · [主線起點至R38：正式基準的形成](../routes/baseline.md) · [現在保存到哪裡](../STATUS.md)

本卡保留原研究與當次保存紀錄；較晚的來源補件及缺件請以[目前狀態](../STATUS.md)為準。已建立閱讀卡不代表這一輪的全部來源已查完。

提高統計項能否修復R33的灰階與銳利度

目標本身變化小，增加權重未恢復細節；負結果需保留

## 必要來源

R33起始模型、實際訓練設定及對應來源

## 影像保存理由

灰階對比和邊緣寬度並列，不能以顯示拉伸代替改善

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

- [原始報告：R33ContrastFix 歷史封存與恢復入口](<../../../Experiments/R33ContrastFix/ARCHIVE_POINTER_20260824.md>)
- [原始報告：R33c — Contrast Fix (W_STAT Increase)](<../../../Experiments/R33ContrastFix/MANIFEST.md>)
- [原始報告：R33 Contrast Fix — W_STAT 提高（已否定）](<../../../Experiments/R33ContrastFix/README.md>)

## 重做與驗證範圍

程式、設定、完整表格與選定影像依保存清單收錄；大型必要來源和固定模型由附件恢復。
本次沒有重跑這一輪全部歷史訓練。可攜執行、完整數值重算與來源逐份核對的實測範圍，請看總入口的驗證紀錄。
任何仍須讀取僅存在D／H原工作區的檔案，都不能列為僅靠GitHub已完整重現。

## 2026年10月16日保存核對

本輪入選的方法、設定、完整數值與代表影像已完成逐份內容核對並保存到GitHub；共用來源與先前移到H槽的歷史版本，按總入口的附件索引取回。

本次完成保存與完整檔案內容核對，沒有重跑本輪全部歷史訓練；原成功、失敗、中止及限制照原報告保留。

D槽副本移除遭執行工具拒絕，本輪沒有因這次整理而被清理。

## 2026年10月21日精選閱讀

[本輪代表影像、失敗影格與完整量測](../project_completion/curated/EARLY_RECON_SELECTION.md)分清模型輸出與相機原拍。一般版本不再附整套逐張重建；完整舊圖由固定歷史取回，原量測明細、方法圖與科學判決保留。重新分析整套前，需先取回完整序列，不能把少數代表圖當成全部資料。


---

[上一個閱讀入口：main/R32Sandbox](main__R32Sandbox.md) · [回本分區](../routes/baseline.md) · [下一個閱讀入口：main/R33RobustLoss](main__R33RobustLoss.md)
