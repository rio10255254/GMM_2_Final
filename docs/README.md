# 文件地圖與名詞表

[專案首頁](../README.md) · [資料夾地圖](navigation/PROJECT_MAP.md)

## 文件分工：每份文件只做一件事

| 文件 | 回答的問題 | 變動頻率 |
|---|---|---|
| [README.md](../README.md) | 這是什麼？結論？去哪找？ | 很少 |
| [PROJECT_ARCHITECTURE.md](../PROJECT_ARCHITECTURE.md) | 系統怎麼設計？怎麼判斷好壞？何時能升級？ | 規則改變時 |
| [PROJECT_STATE.md](../PROJECT_STATE.md) | **現在**用哪個模型？結果？缺什麼？ | 每次有新結論 |
| [ESTIMATOR_POLICY.json](../ESTIMATOR_POLICY.json) | 機器可讀的正式身分與數字（**最高權威**） | 升級／新結論時 |
| [Experiments/INDEX.md](../Experiments/INDEX.md) | 每個實驗的狀態一覽 | 每輪完成時 |
| [reproducibility/EXPERIMENTS.md](reproducibility/EXPERIMENTS.md) | 研究怎麼一路走到現在？某階段看哪裡？ | 很少 |
| [navigation/PROJECT_MAP.md](navigation/PROJECT_MAP.md) | 這個資料夾放什麼？ | 很少 |
| 各輪 `Experiments/R##/reports/` | 該輪的**正式**結論（唯一可編輯處） | 該輪期間 |

衝突時的優先順序：**各輪正式報告 ＞ ESTIMATOR_POLICY.json ＞ PROJECT_STATE.md ＞ 其他入口頁**。`docs/evidence/` 等副本可能落後，不能覆蓋原報告。

## docs/ 底下

| 子資料夾 | 內容 |
|---|---|
| `reproducibility/` | 研究閱讀與保存：逐輪閱讀卡、沿革、資料取得、缺件、各次保存收據。保存收據只證明當時範圍，**日常可略過** |
| `operations/` | 維護規則：新實驗指南、正本規則、已知怪癖、儲存與封存 |
| `navigation/` | 資料夾地圖與深層目錄導讀 |
| `policy/` | PSF 標準等專項政策 |
| `evidence/`、`analysis/` | 穩定引用副本與跨輪分析 |
| `history/` | 被取代的舊敘事與整理前版本（唯讀） |
| `archive/` | 固定快照，如 `docs/archive/legacy_runtime_status/`（較早的程序狀態，不取代 PROJECT_STATE） |
| `superpowers/`、`runtime/`、`presentations_assets/` | 工具產物與簡報素材 |

## 名詞表

### 光學與影像

| 名詞 | 白話解釋 |
|---|---|
| **PSF** | 點擴散函數。顯微鏡拍一個極小亮點時，亮點會變成一小團糊，這團糊的形狀就是 PSF。影像可看成「真實場景被 PSF 糊掉」的結果 |
| **FOV／25 PSF／100 PSF** | 視野不同位置糊法不同，所以量多個位置。主線用 100 格點的 Whole-FOV；R152 用 25 顆（5×5） |
| **Zernike／BADS** | PSF 擬合法：用 Zernike 多項式描述像差，用 BADS 最佳化調係數（`PSF_Fitting/`，MATLAB） |
| **Wiener 反捲積** | 已知 PSF 反推清楚影像的經典公式；模型裡只保守混合使用 |
| **RAW** | 沒有經過任何模型處理的相機原圖，論文共同比較基準 |
| **SEM** | 掃描式電子顯微鏡，提供物體真實尺寸／輪廓的參照；有些輪次的 SEM 同時用於訓練或校正，則不是獨立驗證 |
| **合成資料** | 程式畫乾淨場景，用 PSF 弄糊並加雜訊，生成「糊圖→乾淨圖」配對 |

### 量測

| 名詞 | 白話解釋 |
|---|---|
| **PI** | 位移平台（文件一律簡稱 PI）。它回報自己的位置，稱 **PI 回授**，是位移的參考 |
| **GMF**（repo 內寫法不一） | 公司端固定使用、**不能修改**的外部定位工具（GmmVisionTool）裡的演算法：輸入環形影像，輸出環的亞像素中心座標。全名在檔案中有三種寫法：Geometric Matching Feature（最常見）、Geometric Matching Function、Gaussian Mixture Field，功能描述一致。正因為工具固定，專案要調的是重建模型，而不是工具 |
| **step_std** | 早期指標：連續影格位置的差再求標準差，越小越穩 |
| **0.08／0.8／8 px** | 早期評分的三種位移尺度，對應實際平台位移 0.01／0.1／1 µm（資料夾名如 `pitch0p1um_y_60`）；0.8 px（0.1 µm）是主戰場 |
| **均華、HS100MG、Step、100MG** | 不同來源或樣品的實拍資料。均華提供 202 張 1 µm Y 向實拍，用來驗證交付的 ONNX 模型；Step、100MG 是不同樣品，各有自己的分析資料夾，不能混用 |
| **單趟 30 步波動** | 論文主要指標：一趟 30 步的步距標準差，30 趟合併 |
| **重拍波動** | 同一物件重拍 30 趟，直徑或輪廓讀值的差異 |
| **720 方向** | 輪廓沿圓周取 720 個角度（舊的 360 已淘汰） |
| **外部 vs 內部** | 外部＝獨立量測程式在真實資料上的結果（裁判）；內部＝訓練中的快速分數（`seq_val`、`ann_seq`…），只能篩選 |

### 模型與訓練

| 名詞 | 白話解釋 |
|---|---|
| **MOSR** | 論文中本研究模型的名稱；repo 沒有統一全名。論文表中的 MOSR 就是 R152（參數量相同 1,207,105）。`LabSystem_MOSR` 沿用此詞 |
| **GeoEdgeAlignSR** | 第一代共用主線模型（`Model/`），到 COMBO 為止 |
| **checkpoint／權重** | 訓練中存下的模型。`best_tradeoff`、`latest` 是不同準則的版本，**best 不等於正式採用** |
| **凍結** | 訓練時不更新的部分；R152 凍結 R148v2 全部權重 |
| **Winsorize p95** | 壓低最極端 5% 像素對損失的影響 |
| **8px gate／warmup** | 序列訓練只在訊號夠強、並先暖身後才啟用，避免弱訊號雜訊破壞訓練 |
| **權重平均 avg_aXXX** | 兩個模型權重按比例混合（如 α=0.25） |
| **EMA** | 指數移動平均權重 |
| **分塊推論 512／24** | 大圖切塊，核心 512 像素、各邊多留 24 像素再拼回 |

### 身分與編號

| 名詞 | 意思 |
|---|---|
| **正式基準／核准替代／研究候選／證偽結案** | 見 [ARCHITECTURE §4](../PROJECT_ARCHITECTURE.md)。失敗結果刻意保留 |
| **COMBO** | R33 的 Winsorize p95 + R38v2 序列訓練（8px 門檻 + 暖身）合併 |
| **R##** | 研究輪次；**同號可能是不同系統**（主 R39 ≠ Lab R39；R80 有兩個研究） |
| **主專案／Lab** | 主專案＝最早的工業資料條件；Lab＝後來換成實驗室自己的顯微系統（`Thesis_MOSR_Evidence/LabSystem_MOSR/`） |
| **stage01…33** | Lab 的資料**類型**編號，不是 33 次訓練 |
| **V41／V42** | Lab 程式／模型版本，與主專案 R41／R42 無關；V42 是 R152 之前的論文模型 |
| **R34／35／37、R36** | R34/35/37 只在歷史分支；主專案 R36 至今找不到 |
| **sandbox/r##** | 每個實驗專屬 git 分支命名 |

> 本頁 2026-10-24 改寫前的原文逐位元組保留在 [docs__README.md](history/BEFORE_PLAIN_REWRITE_20261024/docs__README.md)。
