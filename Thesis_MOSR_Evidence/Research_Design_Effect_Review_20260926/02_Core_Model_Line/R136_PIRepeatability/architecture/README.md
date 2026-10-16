# R136 PI referenced repeated displacement

**三組完整LSC已完成：[原圖／R61／R129比較](reports/R136_LSC_RESULTS.md)。以下先行結果與R61閱讀包保留為歷史版本。**

**主結果已改用論文LSC圓心定位：[原圖／R61完整結果](reports/R136_LSC_R61_RESULTS.md)。先前區域影像比對只作補充，不能與LSC數字混用。**

Shared-mainline analysis of 30 complete 31-frame captures. Raw, fixed R61 v16 PSF-off and fixed R129 step8192 original80/16 output. No training or per-result model selection. Full details: config/plan.json; results/status_*.json; reports/R136_RESULTS.md. Branch codex/r136-pi-repeatability.

## 原圖／R61完整先行結果

[30次統計與論文圖表](reports/R136_R61_RESULTS.md)已完成；R129維持背景執行。

## 可攜閱讀成果包

[完整ZIP](output/R136_LSC_R61_Reading_Package.zip)包含18頁PDF、14分頁Excel、全部統計CSV、原尺寸圖表、圓心與邊界點。依使用者選擇不含全量照片或模型；本版僅完整Raw/R61 LSC，R129後續另列。

## Raw與R129專用圖表

[7張PNG/SVG圖表包](output/R129_vs_Raw_LSC_Charts.zip)依使用者要求只含Raw與R129的LSC比較，不含PDF。

## R129不確定度評估

[現有資料可量化的部分](reports/R136_R129_UNCERTAINTY_RESULTS.md)：完整60個位置的重拍分量、平均偏差與時間模型內不確定度；缺少PI與尺度校正，未宣稱完整總不確定度。

## R128追加測試（2026-09-18）

同批930張、同9圓LSC追加R128；進度results/status_R128.json、results/lsc/r128_extension/status.json。新增重建存H槽，results/R128保留入口。前三組報告與壓縮包保持原樣。

## 四組完整LSC（追加R128）

[四組報告](reports/R136_LSC_FOUR_MODEL_RESULTS.md)及[四組結果包](output/R136_LSC_Four_Method_Results.zip)完成。原三組報告與PDF/ZIP保留，未改動另一個訓練程序。
