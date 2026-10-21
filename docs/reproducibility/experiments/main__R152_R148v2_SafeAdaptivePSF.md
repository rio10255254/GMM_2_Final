# main/R152_R148v2_SafeAdaptivePSF 研究與重做紀錄

保存R148v2效益並加入有作用的論文光學模組

8192擴充與930完成；位移／重拍收益保留，尺寸偏大與較慢成本不可省略

## 精選的必要來源（2026-10-21）

[實際使用的25顆光學常數](../../../Experiments/R152_R148v2_SafeAdaptivePSF/calibration/measured_psf_bank.npz)只有731,114 bytes，與原BANK_LOCK記錄的內容身分、5×5排列相同，保留SEM幾何來源限制。這是模型固定成像條件，不是逐張完整重建影像；原訓練影像形成方式與既有重建紀錄仍由原報告說明，不重新上傳整套訓練圖。

可攜原入口需要的基底參照與實際部署模型，均可引用已發布的精確相同檔案，見[關鍵模型逐項來源](../project_completion/curated/KEY_MODEL_REFERENCES.json)。原報告五張實際PSF／同區影像／重拍輪廓圖已在GitHub，直接保留連結；尺寸代價與資料依賴一起留下，不用少量代表圖宣稱整套歷史訓練已重新執行。

## 必要來源

可獨立重建的9216影像配方、精確PSF、基底／擴充模型、930原圖與完整讀值

## 影像保存理由

同視野原圖／重建、實際25PSF、30趟輪廓、尺寸與不利結果

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

- [原始報告：R152 模型架構與完整實驗資料紀錄](<../../../Experiments/R152_R148v2_SafeAdaptivePSF/reports/R152_COMPLETE_MODEL_AND_EXPERIMENT_RECORD_20260929.md>)
- [原始報告：R152完整訓練影像生成程式與重新生成核對](<../../../Experiments/R152_R148v2_SafeAdaptivePSF/reports/R152_DATA_GENERATION_REPRODUCTION_20261004.md>)
- [原始報告：R152：保留 R148v2 效果的自適應 PSF 安全擴充](<../../../Experiments/R152_R148v2_SafeAdaptivePSF/reports/R152_DESIGN_AND_PREFLIGHT.md>)
- [原始報告：R152 完整實拍驗證](<../../../Experiments/R152_R148v2_SafeAdaptivePSF/reports/R152_FULL_REAL_VALIDATION.md>)
- [原始報告：R152 與 RAW 完整研究設計及驗證紀錄](<../../../Experiments/R152_R148v2_SafeAdaptivePSF/reports/R152_RAW_FULL_RECORD_20261002/REPORT.md>)
- [原始報告：R152與RAW研究紀錄閱讀入口](<../../../Experiments/R152_R148v2_SafeAdaptivePSF/reports/R152_RAW_FULL_RECORD_20261002/START_HERE.md>)
- [原始報告：30 趟重拍的單趟 30 步位移波動](<../../../Experiments/R152_R148v2_SafeAdaptivePSF/reports/R152_SINGLE_SCAN_STEP_SD_20260930.md>)
- [原始報告：R152獨立模型與完整訓練資料包](<../../../Experiments/R152_R148v2_SafeAdaptivePSF/reports/R152_STANDALONE_PACKAGE_20261004.md>)
- [原始報告：R152論文三項實際圖像補件](<../../../Experiments/R152_R148v2_SafeAdaptivePSF/reports/R152_THESIS_VISUAL_EVIDENCE_20261003/FIGURE_NOTES.md>)
- [原始報告：2026-09-24：讓 SEM 外框卷積後更接近完整實拍柱子](<../../../Experiments/R152_R148v2_SafeAdaptivePSF/reports/R152_THESIS_VISUAL_EVIDENCE_20261003/calibration/README_TW.md>)
- [原始報告：R152正式訓練改讀TIFF影像檔](<../../../Experiments/R152_R148v2_SafeAdaptivePSF/reports/R152_TIFF_TRAINING_PACKAGE_20261004.md>)
- [原始報告：R152 完整訓練結果與完成後核對](<../../../Experiments/R152_R148v2_SafeAdaptivePSF/reports/R152_TRAINING_RESULTS.md>)

## 重做與驗證範圍

程式、設定、完整表格與選定影像依保存清單收錄；大型必要來源和固定模型由附件恢復。
本次沒有重跑這一輪全部歷史訓練。可攜執行、完整數值重算與來源逐份核對的實測範圍，請看總入口的驗證紀錄。
任何仍須讀取僅存在D／H原工作區的檔案，都不能列為僅靠GitHub已完整重現。

## 2026年10月16日保存核對

本輪入選的方法、設定、完整數值與代表影像已完成逐份內容核對並保存到GitHub；共用來源與先前移到H槽的歷史版本，按總入口的附件索引取回。

本次已實跑本輪的完整資料生成或保存觀測重算；實測範圍見總入口，並不表示重跑過所有歷史訓練。

D槽副本移除遭執行工具拒絕，本輪沒有因這次整理而被清理。

## 資料生產方法與共用來源

[本輪原生產／讀取程式、設定與修正紀錄](../GENERATION_GUIDE.md)已按實際來源確認；基礎來源：本輪獨立生成／原獨立生產包。可再生的大檔不必上傳整套。原絕對位置與固定內容身分供歷史追查，日後在新的研究副本設定自己的來源位置；新生成內容與原件不同時須保留差異，不改寫舊結果。
