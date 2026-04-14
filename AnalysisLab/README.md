# AnalysisLab

## 這是什麼

`AnalysisLab/` 是 GeoEdge 超解析模型的**幾何品質分析中心**。

GeoEdge 是一個 AI 超解析模型，用來對顯微鏡拍攝的環形結構（annulus）影像做反卷積重建。重建的目標不是讓影像「好看」，而是讓環形邊界足夠銳利，使下游的 GMF（Geometric Matching Feature，全環模板匹配）定位演算法能精準追蹤幀間的亞像素位移。

本目錄收納所有版本的模型分析——包括分析腳本、自動化測試、圖表結果、JSON 數據摘要、以及人類可讀的中文分析報告。設計上確保即使不跑任何程式碼，只看 `results/` 裡的圖片和 `reports/` 裡的 Markdown 報告，就能完整理解每個版本的幾何品質。

整體導覽與總體健康請回 `python Tools/project_control_center.py`；本 README 只負責 AnalysisLab 自己的分析入口。

## 設計原則

### 版本優先（Version-First Layout）

第一層目錄永遠按模型版本展開：`r26/`、`r30/`、`r32/`……。這樣做的好處是：
- 不同版本的分析完全獨立，不會互相干擾
- 同一個版本的所有分析（單張、序列、未來可能的多 FOV 分析）都收在同一個目錄下
- 比較版本時，只需要並排打開兩個版本的報告

### 類型次之

每個版本下再按分析類型分層：`single_image/`（單張靜態分析）、`sequence/`（多幀時序分析）。每種分析類型都有相同的子目錄結構，方便找到東西。

### 自含 vs 外部依賴

- **自含分析**（如 `single_image/`）：demo 影像直接 tracked 在 `inputs/` 和 `recon/` 中，任何人 clone 就能跑
- **外部依賴分析**（如 `sequence/`）：原始影像太大不適合 tracked，路徑宣告在 `configs/dataset_config.py`。但分析結果（圖表 + JSON + 報告）是 tracked 的

## 目錄總覽

```
AnalysisLab/
├── README.md                    # 本檔案：整體說明
├── index.json                   # 機器可讀的結構索引（CI 或工具用）
├── tests/
│   └── test_analysis_lab_layout.py   # 結構合約測試：確保目錄結構符合規範
│
└── r26/                         # ── R26 模型 ──────────────────────
    ├── README.md                # R26 分析總覽：模型背景 + 兩條分析線摘要
    │
    ├── single_image/            # 單張影像幾何分析
    │   ├── README.md            #   本分析的完整說明
    │   ├── scripts/             #   run_single_image_analysis.py
    │   ├── tests/               #   5 項 pytest
    │   ├── inputs/              #   tracked demo input（BMP + preview）
    │   ├── recon/               #   tracked R26 重建結果（BMP + preview）
    │   ├── results/             #   8 張分析圖表 + analysis_summary.json
    │   └── reports/             #   R26_SingleImage_Analysis_Report.md
    │
    ├── sequence/                # 多幀序列穩定性分析
    │   ├── README.md            #   本分析的完整說明
    │   ├── scripts/             #   run_sequence_analysis.py
    │   ├── tests/               #   8 項 pytest
    │   ├── configs/             #   dataset_config.py（外部路徑宣告）
    │   ├── results/             #   3 dataset × 9 檔 + cross_dataset × 4 檔
    │   └── reports/             #   R26_Sequence_Analysis_Report.md
    │
    └── performance/             # 跨設備效能基準測試
        ├── README.md            #   完整使用教學（含不同設備部署步驟）
        ├── scripts/             #   inference / training / cross-device compare
        ├── tests/               #   4 項 pytest
        ├── configs/             #   device_config.py（每台設備只改這個）
        ├── results/             #   每台設備一個子目錄 + cross_device 匯總
        └── reports/             #   R26_Performance_Report.md
```

## 每個分析目錄的固定子結構

| 子目錄 | 放什麼 | tracked? | 備註 |
|--------|--------|----------|------|
| `scripts/` | 分析入口腳本 | Yes | 一個 `.py` 就是一條完整分析管線 |
| `tests/` | pytest 測試 | Yes | 驗證核心函式的正確性和結果不退化 |
| `inputs/` | 輸入影像 fixture | Yes | 自含分析才有 |
| `configs/` | 外部資料路徑宣告 | Yes | 外部依賴分析才有 |
| `recon/` | 重建輸出 fixture | Yes | 自含分析才有 |
| `results/` | PNG 圖表 + JSON 摘要 | Yes | 即使不跑腳本也能閱讀 |
| `reports/` | 中文 Markdown 分析報告 | Yes | 含數據表格、解讀、裁決、侷限性 |

## 目前收錄的分析

| 版本 | 分析線 | 內容摘要 | 圖表數 | 測試 |
|------|--------|---------|--------|------|
| R26 | `single_image` | 單張 demo 的邊界殘差、諧波、熱點、邊緣寬度分析 | 8 | 5 pass |
| R26 | `sequence` | 三尺度序列的步進穩定性、k=2 穩定性、偏移漂移、殘差一致性、熱點持續性 | 30 | 8 pass |
| R26 | `performance` | 跨設備推論/訓練效能基準測試（延遲、吞吐量、GPU 記憶體、數值一致性） | — | 4 pass |

## index.json

`index.json` 是機器可讀的結構索引，記錄每個版本的每條分析線的入口路徑（script、test、report、results_dir）。用途是讓 CI、Claude Code、或其他工具能自動找到正確的檔案，不需要硬寫路徑。

## 快速開始

整體巡檢請回控制中心；下面這些命令只針對 AnalysisLab。

```bash
# 跑所有測試（驗證結構合約 + 分析正確性）
pytest AnalysisLab/ -q

# 跑單張分析（自含，不需要外部資料）
python AnalysisLab/r26/single_image/scripts/run_single_image_analysis.py

# 跑序列分析（需要 dataset_config.py 中的外部路徑可達）
python AnalysisLab/r26/sequence/scripts/run_sequence_analysis.py
```

## 未來擴充

當新版本（如 R30、R32）需要分析時：

1. 建立 `AnalysisLab/r30/`，複製 `r26/` 的子目錄結構
2. 在 `index.json` 的 `versions` 中註冊新版本
3. 更新本 README 的收錄表
4. 如果有新的分析類型（例如 `multi_fov/`），在對應版本下新增子目錄

設計上不需要修改任何既有版本的結構或程式碼。
