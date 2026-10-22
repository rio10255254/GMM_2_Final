# main/R63_CausalBoundaryMotionAblation：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R63_CausalBoundaryMotionAblation.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：拆開幾何、位移與安全上採樣的貢獻。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R63 MOSR 因果消融實驗報告](<reports/R63_RESULTS.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [CHART_MAP.md](<CHART_MAP.md>) | 1檔 | R63 Chart Map |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R63 Manifest |
| [PROTOCOL.md](<PROTOCOL.md>) | 1檔 | R63 Pre-registered Protocol |
| [PROTOCOL_REVISION_LOG.md](<PROTOCOL_REVISION_LOG.md>) | 1檔 | R63 Protocol Revision Log |
| [README.md](<README.md>) | 1檔 | Round 63 — Causal Boundary and Motion Ablation |
| [REPORT_PLAN.md](<REPORT_PLAN.md>) | 1檔 | R63 Technical Report Plan |
| [reports/](<reports/README.md>) | 2檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results/README.md>) | 838檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts/README.md>) | 38檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [tests/](<tests>) | 5檔 | 原檢查程式；不是研究結果本身 |

## 必要來源與取得界線

共同起點、兩個種子、固定分組、各消融設定與光學來源。

原訓練名單的complete=true表示當時完成訓練；不代表今天32個選中模型都還在。現在已保存31個，原第24輪的其中一個模型仍缺。[缺件與原清理證據](<../../docs/reproducibility/round_source_followthrough_20261022/README.md>)。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
