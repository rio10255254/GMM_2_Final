# main/R136_PIRepeatability：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R136_PIRepeatability.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：用30趟重拍檢查固定模型的位移與不確定度。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R136：原圖、R61、R129、R128的完整LSC位移比較](<reports/R136_LSC_FOUR_MODEL_RESULTS.md>)
- [R136：LSC圓心定位的30次位移比較](<reports/R136_LSC_R61_RESULTS.md>)
- [R136：LSC圓心定位的30次位移比較](<reports/R136_LSC_RESULTS.md>)
- [R136第二次核對：這份新實拍對模型能力判斷的影響](<reports/R136_MODEL_ASSESSMENT.md>)
- [R128：十字中心附近九顆 pillar 的重複度詳表](<reports/R136_R128_CORNER9_DETAIL.md>)
- [R129不確定度評估：現有資料可量化的部分](<reports/R136_R129_UNCERTAINTY_RESULTS.md>)

其餘原報告見[本輪完整研究卡](<../../docs/reproducibility/experiments/main__R136_PIRepeatability.md>)。

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [config/](<config/README.md>) | 2檔 | 實驗設定、條件與來源鎖定 |
| [HANDOFF.md](<HANDOFF.md>) | 1檔 | R136 continuation |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R136 manifest |
| [output/](<output>) | 35檔 | 輸出內容，依原報告確認用途 |
| [README.md](<README.md>) | 1檔 | R136 PI referenced repeated displacement |
| [reports/](<reports/README.md>) | 35檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results/CONTENTS.md>) | 969檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts/README.md>) | 60檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |

## 必要來源與取得界線

930原圖及PI讀值、各固定模型、原始圓心／邊界點與比例。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
