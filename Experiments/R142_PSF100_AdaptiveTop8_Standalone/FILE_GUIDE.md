# main/R142_PSF100_AdaptiveTop8_Standalone：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R142_PSF100_AdaptiveTop8_Standalone.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：擴為100顆並逐張選八顆。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R142_PSF100_AdaptiveTop8_Standalone 研究保存清單](<MANIFEST.md>)
- [自適應 PSF 四次修正 U-Net 技術卡](<MODEL_CARD.md>)
- [包裝修訂記錄](<PACKAGING_CHANGELOG.md>)
- [100 顆 PSF 自適應選八顆獨立包](<README.md>)
- [BANK_REQUIRED.md](<calibration/BANK_REQUIRED.md>)
- [R142 封裝驗證](<results/PACKAGE_VALIDATION.md>)

其餘原報告見[本輪完整研究卡](<../../docs/reproducibility/experiments/main__R142_PSF100_AdaptiveTop8_Standalone.md>)。

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [calibration/](<calibration>) | 1檔 | 校正及固定光學來源紀錄 |
| [config/](<config>) | 3檔 | 實驗設定、條件與來源鎖定 |
| [dataset.py](<dataset.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [derive_weights.py](<derive_weights.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [evaluation/](<evaluation>) | 310檔 | 量測介面、固定參照、設定或比較內容 |
| [infer.py](<infer.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [install_bank.py](<install_bank.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [losses.py](<losses.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R142_PSF100_AdaptiveTop8_Standalone 研究保存清單 |
| [model.py](<model.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [MODEL_CARD.md](<MODEL_CARD.md>) | 1檔 | 自適應 PSF 四次修正 U-Net 技術卡 |
| [optical/](<optical>) | 2檔 | 光學計算與配套 |
| [PACKAGING_CHANGELOG.md](<PACKAGING_CHANGELOG.md>) | 1檔 | 包裝修訂記錄 |
| [README.md](<README.md>) | 1檔 | 100 顆 PSF 自適應選八顆獨立包 |
| [results/](<results>) | 1檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [tests/](<tests>) | 5檔 | 原檢查程式；不是研究結果本身 |
| [train.py](<train.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [training_policy.py](<training_policy.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [utils.py](<utils.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [verify_package.py](<verify_package.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |

## 必要來源與取得界線

未訓練起點、安裝條件與缺件紀錄，不能放測試PSF充數。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
