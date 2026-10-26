# R32：加入真實影像訓練，內部全過，外部差了將近一倍

[研究時間線](<../../docs/research/TIMELINE.md>) · [前任基準 R30](<../../docs/reproducibility/experiments/legacy__round30.md>) · [下一輪 R33](<../R33RobustLoss/FILE_GUIDE.md>) · [完整原始說明（中英對照）](<README.md>)

**一句話：** 從前任基準 R30 出發，訓練時以 30% 的機率把合成影像換成真實顯微影像，希望模型習慣真實感測器的紋理。內部的合成資料探針全部通過，但外部真實資料的 0.8px 步距波動比 R30 差了 97.7%，三個尺度全部退步。這一輪讓之後的研究很長一段時間都刻意不把真實影像放進訓練。

| | |
|---|---|
| 結果 | **未採用**（外部 `FAIL`） |
| 候選名稱 | `r32_real_eq_finetune`；`profiles_r32.py` 另定義了兩個候選，但這次只執行了這一個 |
| 時間 | 2026-03-19 訓練與內部稽核，03-20 外部比較 |
| 實驗條件 | A：公司端環形影像 + 外部 GMF |
| 起點 | R30（`r30_b1_dironly`） |

## 在研究裡的位置

R30 是當時的正式基準，R31 調整損失權重後外部退步了 6～10%。R32 換一個方向：既然最後要量的是真實影像，那就讓模型在訓練時直接看到真實影像。

這一輪放在獨立的沙盒裡做（訓練程式、稽核、狀態機都在本資料夾內），避免實驗性的改動影響共用的 `Model/`。

## 這輪在問什麼

在 R30 的基礎上，把真實影像加進等化（EQ）訓練訊號，能不能讓模型在真實量測資料上表現更好？

## 怎麼做

- 從 `Training_Data/generated_convolved/Real_Image/` 載入真實顯微影像，隨機裁切 256×256。
- 每個訓練步以 30% 的機率，把 EQ 損失的輸入換成真實影像。
- 學習率很低（1.1×10⁻⁶），屬於微調；40 輪掃描，每輪做 GMF 驗證。
- 先用合成資料做內部 0.8px 與 8px 探針稽核，通過後才送外部真實資料比較。

## 結果

**內部稽核**（合成資料）：全部通過。0.8px 中心誤差比例 0.798（門檻 > 0.25）、步長誤差 0.110（門檻 < 0.45）；8px 步長誤差 0.097（門檻 < 0.30）、方向一致率 0.865（門檻 > 0.756）。

**外部 GMF**（真實資料，步距標準差，px）：

| 尺度 | R30 | R32 | 變化 |
|---|---:|---:|---:|
| 8px | 0.205193 | 0.319667 | +55.8% |
| 0.8px（主尺度） | 0.167862 | 0.331821 | **+97.7%** |
| 0.08px | 0.157720 | 0.230119 | +45.9% |

## 讀這些數字要知道的事

1. **這是「內部通過、外部失敗」最清楚的一次。** 內部稽核全用合成資料，外部用的是真實顯微影像，雜訊和紋理分布完全不同。原始說明推測的原因是：真實影像讓模型過度適應，反而破壞了 R30 原本在真實資料上的泛化能力；極低學習率下也可能過擬合了合成資料的特性。這是推測，沒有另外實驗驗證。
2. **用的是舊的離群值規則。** 這一輪的比較腳本用 3σ 規則排除離群步；0.8px 的正式數字 0.331821 是原始值，排除 1 步後是 0.303349。R33 之後改成只排除 z > 5 的 GMF 工具失敗，見 [GMF 量測方法](<../R33RobustLoss/reports/GMF_STEP_STD_METHODOLOGY.md>)。
3. **影響了之後的研究方向。** R39、R40 都明確寫著「刻意不碰真實影像」，理由就是 R32。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 內部稽核、決策備忘、外部比較的原始報告 | 本資料夾 [reports/](<reports>)，已在 GitHub |
| R32 選用的模型（約 50 MB） | Release [`research-round-source-followthrough-20261022`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-round-source-followthrough-20261022)，只需下載約 60 MB；見[逐輪補件說明](<../../docs/reproducibility/round_source_followthrough_20261022/README.md>) |
| 100 張真實 EQ 輸入 | 同一個 Release，約 40 MB |
| 訓練與稽核程式、啟動腳本 | 本資料夾 [Model/](<Model>)、[Tools/](<Tools>)，流程見[原始說明](<README.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的缺口：** 這 100 張真實 EQ 輸入是處理過的固定版本。從相機原拍到這個處理版本的完整對照沒有找到，所以能取得當年用的輸入，但不能證明當年全部的前處理內容。見[缺件清單](<../../docs/reproducibility/KNOWN_GAPS.md>)。

## 原始報告

| 報告 | 什麼時候讀 |
|---|---|
| [原始說明](<README.md>) | 最完整的一份：沙盒結構、候選、五階段流程、訓練設定、稽核指標、內外差異（中英對照） |
| [外部比較](<reports/ROUND32_EXTERNAL_COMPARE.md>) | 三尺度、自相關、離群值與最終判定 |
| [內部決策備忘](<reports/ROUND32_DOMAIN_CAPACITY_DECISION_20260319_183614.md>) | 內部探針的門檻與結果 |
| [0.8px 稽核](<reports/ROUND32_DOMAIN_CAPACITY_AUDIT_0P8_SUMMARY_20260319_183506.md>)、[8px 稽核](<reports/ROUND32_DOMAIN_CAPACITY_AUDIT_8P0_SUMMARY_20260319_183546.md>)、[彙總](<reports/ROUND32_DOMAIN_CAPACITY_SUMMARY_20260319_183506.md>) | 內部探針的細節 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R32Sandbox.md>)；H 槽完整封存見[封存紀錄](<ARCHIVE_POINTER_20260824.md>)。早期批次裡的 R32 輸出另見 [legacy round32](<../../docs/reproducibility/experiments/legacy__round32.md>)，正式可編輯的紀錄以本資料夾為準。

## 資料夾裡有什麼

| 位置 | 內容 |
|---|---|
| [Model/](<Model>) | R32 專用的訓練、稽核、資料載入與外部比較程式 |
| [Tools/](<Tools>) | 啟動、監看與外部重建的 PowerShell 腳本 |
| [reports/](<reports>) | 稽核、決策與外部比較 |
| [runtime/](<runtime>) | 執行狀態紀錄 |
| [artifacts/](<artifacts>) | 訓練輸出的說明（權重本身在 Release） |
| [external_compare/](<external_compare>) | 外部比較的中間產物 |
| [MANIFEST.md](<MANIFEST.md>) | 研究保存清單 |
