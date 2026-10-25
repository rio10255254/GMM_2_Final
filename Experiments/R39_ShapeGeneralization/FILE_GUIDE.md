# R39：讓模型不只會圓環，以及核准替代 R39R40_a025 的由來

[研究時間線](<../../docs/research/TIMELINE.md>) · [起點 COMBO](<../R38v2SeqFixed/FILE_GUIDE.md>) · [下一輪 R40](<../R40_MicroscopyFeatureCoverage/README.md>) · [後續 R46](<../R46_CornerAwareFineTune/FILE_GUIDE.md>) · [Lab 同名 R39（不同實驗）](<../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R39_ShapeGeneralization/>) · [正式身分登記](<../../ESTIMATOR_POLICY.json>)

**一句話：** COMBO 對圓環很強，遇到三角形、矩形、多邊形就明顯變差。R39 加入受控的合成多形狀資料重新微調，形狀大幅進步，但環形定位退步；接著把訓練結果和 COMBO 的權重做線性平均，找回環形穩定度，同時保留一部分形狀能力（a030）。後來再把 a030 跟 R40 的 a043 平均，得到 R39R40_a025：三個外部尺度第一次全部守在 COMBO 的 3% 以內，2026-05-11 升為核准替代。

| | |
|---|---|
| 結果 | 兩個訓練端點 **未採用**；權重平均 a030 **研究候選**（外部 `PASS_TRADEOFF`）；**R39R40_avg_a025 核准替代**（`balanced_full_spectrum_alternate`，2026-05-11） |
| 時間 | 2026-04-28 訓練；a030 外部 GMF 在 5 月初；a025 在 05-11；a025 ONNX 包內容稽核在 05-13 |
| 實驗條件 | A：公司端環形影像 + 外部 GMF；形狀與顯微用合成驗證集 |
| 起點 | COMBO 的 `best_tradeoff`，沿用 R38v2 的 8px 序列門檻 |

主專案這個 R39 跟 LabSystem 的 R39 是兩個不同的實驗，只是同號。

## 在研究裡的位置

COMBO 在 4/8 成為正式基準，但它只在環形影像上驗證過。實際觀察到的弱點是：模型的能力被訓練分布綁死在圓環上，碰到其他形狀就退步。R39 是第一次正面處理這個問題。

這一輪**刻意不碰真實影像**。R32 才剛示範過，加入真實影像可能「內部看起來不錯、外部直接失敗」，所以 R39 先用受控的合成資料探路。

## 這輪在問什麼

在訓練資料裡保留環形、再加入三角形、圓、矩形、橢圓、多邊形和混合場景，能不能把非環形形狀的重建拉起來，同時不傷環形的外部定位？升級規則寫得很硬：**形狀數字再漂亮，環形守門沒過就不升級。**

## 怎麼做

1. **兩個訓練端點**（都從 COMBO 接續 100 輪）：
   - `r39_shape_mix_safe`：1,100 對環形 + 140 對形狀
   - `r39_shape_mix_strong`：1,100 對環形 + 490 對形狀，用來探容量上限
   - 另有 210 對完全沒進訓練的形狀驗證集 `shape_val_unseen`
2. **權重平均：** 兩個端點都從 COMBO 微調出來，預期權重之間是線性連通的。在 COMBO 和 strong 之間取 11 個比例，每個都測形狀與三尺度環形，挑出同時過四個門檻、形狀最好的那個：α = 0.30，也就是 **a030**。
3. **跨輪平均：** a030 跟 R40 的 a043 在外部 GMF 上的取捨方向剛好相反，於是在兩者之間再取 α = 0.25、0.50、0.75 三點，加上兩端共五點。

## 結果

**形狀驗證**（210 對未見過的合成形狀，PSNR）：

| 模型 | PSNR | 對 COMBO |
|---|---:|---:|
| COMBO | 22.84 | — |
| safe | 26.68 | +3.84 |
| strong | 30.07 | +7.23 |
| a030 | 25.03 | +2.19 |
| **a025** | 25.51 | +2.67 |

**環形守門**：兩個訓練端點都退步（safe 的 8px 內部步距標準差 0.369，COMBO 是 0.139），所以沒有送外部 GMF。a030 的三個尺度內部數字都持平或略好於 COMBO。

**外部 GMF**（步距標準差，px，越小越好）：

| 候選 | 8px | 0.8px | 0.08px | 自動判定 |
|---|---:|---:|---:|---|
| COMBO | 0.154515 | 0.131560 | 0.099891 | 正式基準 |
| a030 | 0.143794（−6.9%） | 0.140008（+6.4%） | 0.083941（−16.0%） | `PASS_TRADEOFF` |
| **a025** | 0.146505（−5.2%） | 0.133546（+1.5%） | 0.100400（+0.5%） | **`PASS_UPGRADE_GUARD`** |
| α = 0.50 | 0.151365 | 0.149209（+13.4%） | 0.093177 | 未過 |
| α = 0.75 | 0.144254 | 0.152095（+15.6%） | 0.111468（+11.6%） | 未過 |
| R40 a043（α = 1） | 0.145379 | 0.127411 | 0.121382（+21.5%） | 未過 |

a030 的 0.08px 是當時全專案最低的外部數字。a025 是第一個三個尺度都在 COMBO 3% 以內的候選，之前沒有任何候選做到過。

**a025 升級前補的驗證**：顯微 5 類（PSNR 25.41，COMBO 22.73）、形狀 7 類（25.51，COMBO 22.84）、視覺四項統計（邊緣陡度比 COMBO 低 5.9%，仍屬銳利那一帶，離 R33 的偏軟帶很遠），以及五聯視覺對比圖。

## 讀這些數字要知道的事

1. **權重平均不是平滑插值。** a030 × a043 之間，α = 0.25 在 0.08px 上比兩端都好，α = 0.50、0.75 的 0.8px 卻比兩端都差。用兩端數字線性外推，猜不中中間的結果。
2. **a025 的強項是均衡，不是單項最強。** 0.8px 要極致就用 R33，要視覺就用 R38v2；a025 適合不想在任何一軸做取捨的場合。三者的用途都登記在 [ESTIMATOR_POLICY.json](<../../ESTIMATOR_POLICY.json>)。
3. **能力範圍被訓練資料綁住。** a030 通過外部驗收之後，又拿一張刻意落在訓練分布之外的合成 IC 顯微影像來測。結果兩個模型都把格線抹平、把紋理當雜訊去掉。換成雜訊較輕的輸入，重建也幾乎不變，所以限制不在雜訊或 PSF，而是**資料裡根本沒有這類內容**。這不影響 a030 在「環形 + 簡單形狀」上的判定，但說明它不能當成通用的顯微重建模型。這也直接成了 R40 擴充顯微特徵的理由。
4. **升級決定由專案負責人做。** 報告只記錄量測事實和自動判定的標籤；a030 留在研究候選，a025 由負責人在 05-11 決定升級。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 外部 GMF 分數、各 α 的比較、能力評估表、Rayleigh 診斷 | 本資料夾 [results/](<results>)，已在 GitHub |
| a030 與 a025 的權重（各約 19.5 MB） | Release [`research-results-models-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)；見[模型指南](<../../docs/reproducibility/MODEL_GUIDE.md>) |
| 訓練資料 | 用 `scripts/r39_shape_data.py build --profile all` 重新產生；環形部分來自[早期主線共用環形來源](<../../Shared_Sources/Baseline_Ring_Inputs/README.md>) |
| 權重平均 | `scripts/run_r39_weight_sweep.py`（11 點 sweep，邏輯在 `r39_weight_sweep.py`）、`scripts/r39r40_complementary_average.py`（a030 × a043） |
| 交給公司的 a025 ONNX 包 | [GeoEdge_R39R40_a025_ONNX_Company_Package_20260511](<../../_deployment_package/GeoEdge_R39R40_a025_ONNX_Company_Package_20260511/README.md>)；內容稽核見 [ONNX 包內容稽核](<results/a030_x_a043_sweep/reports/R39R40_A025_ONNX_PACKAGE_CONTENT_AUDIT_20260513.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的缺口與限制：**
>
> - **a025 的 ONNX 模型檔還沒上雲端。** 公司包裡的 `model/geoedge_r39r40_a025_body.onnx`（約 15 MB）不在 GitHub，也不在任何 Release，目前只存在原電腦上。
> - **a025 送外部 GMF 的重建影像**（約 200 張、540 MB）也只在原電腦上。
> - **權重很難單獨拿。** 每個權重只有約 19.5 MB，但目前的打包按檔案大小切分卷，取回其中一個就要下載約 1.4～1.5 GB。整理計畫會處理。
> - **訓練資料**（約 1.7 GB）沒有上傳；可用 builder 重新產生，但沒有逐檔核對過重新產生的資料與原檔相同。

## 原始報告

| 報告 | 什麼時候讀 |
|---|---|
| [R39 結果](<reports/R39_RESULTS.md>) | 兩個端點、環形守門、11 點權重平均、a030 外部 GMF、視覺品質、合成 IC 示範 |
| [a030 外部 GMF 比較](<reports/R39_EXTERNAL_COMPARE.md>) | a030 三尺度的原始比較 |
| [a030 顯微評估](<reports/R39_A030_MICROSCOPY_EVALUATION.md>) | a030 在多樣顯微圖形上的表現，並與 R40 a045 對照 |
| [a030 × a043 互補平均](<results/a030_x_a043_sweep/reports/R39R40_COMPLEMENTARY_AVG_RESULTS.md>) | 五點 sweep 與非線性現象 |
| [a025 全面能力評估](<results/a030_x_a043_sweep/reports/R39R40_AVG_a025_CAPABILITY_EVAL.md>) | a025 升級前的四項驗證 |
| [a025 Rayleigh 診斷](<results/a030_x_a043_sweep/reports/R39R40_AVG_a025_RAYLEIGH_DIAGNOSTIC.md>)、[驗證](<results/a030_x_a043_sweep/reports/R39R40_AVG_a025_RAYLEIGH_DIAGNOSTIC_VALIDATION.md>)、[視覺與分布](<results/a030_x_a043_sweep/reports/R39R40_AVG_a025_RAYLEIGH_VISUAL_AND_DISTRIBUTION.md>) | a025 的細節極限在哪裡，也是 R46 的設計依據 |
| [原始說明](<README.md>) | 當時的動機、資料包與升級規則，原文保留 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R39_ShapeGeneralization.md>)、[原結果對照](<results/SOURCE_RESULTS_GUIDE.md>)與[四輪方法與來源](<../../docs/reproducibility/round_source_reviews/BASELINE_20261023.md>)。

## 資料夾裡有什麼

| 位置 | 內容 |
|---|---|
| [reports/](<reports>) | R39 原始報告 |
| [results/a030_x_a043_sweep/](<results/a030_x_a043_sweep/README.md>) | a025 與跨輪平均的全部結果、報告、視覺對比、ONNX 交付稽核 |
| [results/](<results>) | 形狀驗證、環形守門、權重平均、外部 GMF、合成 IC 示範 |
| [scripts/](<scripts>) | 資料產生、訓練、重建、守門、權重平均、外部比較 |
| [tests/](<tests>) | 資料包與權重平均邏輯的單元測試 |
| [MANIFEST.md](<MANIFEST.md>) | 研究保存清單 |
