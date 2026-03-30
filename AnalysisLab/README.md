# AnalysisLab

`AnalysisLab/` 是常駐、版本優先的分析資料入口。

設計原則：
- 單一入口：所有可長期保留的分析 fixture、腳本、測試、結果與報告都收在這裡
- 版本優先：第一層永遠先按 `r26/`、`r30/`、`r32/` 這種版本展開
- 類型次之：每個版本下再按 `single_image/`、`sequence/` 等分析類型分層
- 可擴充：未來新增版本或分析法時，不需要重設整棵樹

目前已收錄：
- `r26/single_image/`
- `r26/sequence/`

固定結構：
- `scripts/`：分析入口腳本
- `tests/`：pytest 測試
- `inputs/` 或 `configs/`：輸入 fixture 或外部依賴設定
- `recon/`：需要保留的重建輸出
- `results/`：代表性圖表與 JSON 摘要
- `reports/`：人類可讀分析報告

快取與執行垃圾如 `__pycache__/`、`.pytest_cache/` 不屬於常駐 surface。
