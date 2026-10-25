# R38v2 與 COMBO：公司端正式基準的由來

[研究時間線](<../../docs/research/TIMELINE.md>) · [R33～R38v2 完整系列](<../R33RobustLoss/reports/R33_R38v2_COMPLETE_EXPERIMENT_SERIES.md>) · [前一步 R38](<../R38SeqConsistency/README.md>) · [R33](<../R33RobustLoss/README.md>) · [正式身分登記](<../../ESTIMATOR_POLICY.json>)

**一句話：** 這個資料夾裡有兩個模型。R38v2 修好了 R38「序列訓練被弱訊號干擾」的問題，邊緣陡度比前任基準 R30 高 89%；COMBO 則在同一次訓練裡，同時用上 R33 的極端像素限制和 R38v2 的序列訓練，外部 GMF 三個尺度全部通過，0.8px 比 R30 好 21.6%，成為 2026-04-08 起公司端的正式基準。

| | R38v2 | COMBO |
|---|---|---|
| 結果 | **核准替代**（視覺優先） | **採用**（正式基準，2026-04-08 起） |
| 候選名稱 | `8px_gate` | `r38v2_8px_gate_p95` |
| 選中的輪次 | 第 54 輪 | 第 21 輪 |
| 訓練紀錄 | `training_progress_..._20260406_235957` | `training_progress_..._20260408_003525` |
| 實驗條件 | A：公司端環形影像 + 外部 GMF | 同左 |

COMBO 至今仍是公司端的正式基準；論文採用的 R152 是另一條線、另一種評分，兩者不衝突。

## 在研究裡的位置

R30 之後，R33 發現「限制極端像素的拉扯」（Winsorize p95）能讓定位大幅變準，但邊緣變軟。接下來 R34 空間分頻、R35 增強光學反卷積、R37 光學層頻率正則，想把銳利度補回來，全都失敗。

R38 換個方向，直接讓模型學「連續影格之間要一致」。它在 8px 上表現很好，可是 0.8px 和 0.08px 的影格之間差異太小，序列損失等於在灌雜訊，反而把 0.8px 弄壞了。R38v2 就是針對這個問題的修正，COMBO 再把 R33 的機制一起放進來。

## 這輪在問什麼

**R38v2：** 只讓「訊號夠強」的序列參與訓練，能不能保住 R38 在 8px 和邊緣銳利度上的好處，又不弄壞 0.8px？

**COMBO：** 把 R33 的 p95 限制和 R38v2 的序列訓練放進同一次訓練，能不能同時拿到 R33 的定位精度和 R38v2 的銳利度？

## 怎麼做

R38v2 的三項修正：

1. **訊號門檻：** 相鄰影格差異小於 0.002 的批次直接跳過（`SEQ_MIN_DELTA_THRESHOLD=0.002`）。
2. **暖身：** 前 15 輪只學重建，不加序列損失，讓網路先學好銳利度。
3. **只用 8px 序列：** stage_25／26 共 120 對，訊號最強、裁切全部有效。原本 R38 用了 624 對，大多數其實無效。

COMBO 在這之上加入 R33 的 Winsorize p95，並分三段啟用：第 1～10 輪只做重建，第 11～15 輪加入 p95，第 16 輪起才加入序列項。

**COMBO 不是把 R33 和 R38v2 兩個模型的權重平均**（那種做法是後來的 R39R40_a025）。它是一次完整的訓練，同時使用兩種機制。

## 結果

外部 GMF 是固定、不能修改的 GmmVisionTool，看三個位移尺度的步距標準差（px，越小越好）。離群值只排除 z > 5 的 GMF 工具失敗，規則見 [GMF 量測方法](<../R33RobustLoss/reports/GMF_STEP_STD_METHODOLOGY.md>)。

| 尺度 | R30（前任基準） | R33 p95 | R38v2 | **COMBO** | COMBO 對 R30 |
|---|---:|---:|---:|---:|---:|
| 0.8px（主尺度） | 0.167862 | **0.119049** | 0.134205 | **0.131560** | −21.6% |
| 0.08px | 0.157720 | **0.086274** | 0.106457 | 0.099891 | −36.7% |
| 8px | 0.205193 | 0.153343 | **0.143988** | 0.154515 | −24.7% |

R30、R38v2、COMBO 三個尺度都沒有離群值；R33 的 8px 有 2 個 GMF 工具失敗被排除（原始值 0.932763），這是唯一的例外。

**視覺品質**（GMF 只量幾何精度，模型可能過了 GMF 卻看起來很軟，R33 就是這樣，所以一併報告）：

| 指標 | R30 | R33 | R38v2 | **COMBO** |
|---|---:|---:|---:|---:|
| 邊緣陡度 | 4.05 | 3.16 | **7.67** | **7.67** |
| 對比標準差 | 34.64 | 26.49 | 30.92 | **32.35** |
| 梯度強度 | 3.46 | 2.36 | 2.67 | 2.78 |
| 邊緣對比 | 89.1 | 50.8 | 77.5 | 74.1 |

COMBO 的擬合殘差在三個尺度、內外邊界上都是當時的歷史最低（例如 0.8px 內邊界 2.044，R30 是 2.894）。

## 讀這些數字要知道的事

1. **三個候選各有用途。** R33 定位最準但視覺退步；R38v2 視覺最好；COMBO 是兩者之間最均衡的。三者都登記在 [ESTIMATOR_POLICY.json](<../../ESTIMATOR_POLICY.json>)，用途不同、不能互換身分。
2. **內部分數和外部 GMF 不一致。** COMBO 的內部步距標準差 0.178，超過內部門檻 0.168，但外部 GMF 只有 0.132，遠低於門檻。原報告推測是因為殘差降低讓 GMF 的邊緣偵測更準，但這是推測，沒有另外驗證。這也是本專案一再看到的現象：內部分數不能取代外部驗收。
3. **8px 不是最好。** COMBO 的 8px 比 R38v2 差，是以主尺度 0.8px 和整體均衡為優先所做的取捨。
4. **這是條件 A 的分數。** 跟 LabSystem、930 張 PI 重拍的數字是不同的考試，不能直接比。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 外部 GMF 回傳、比較表、720 角度序列分析 | 本資料夾 [results/](<results>)，已在 GitHub |
| COMBO 與 R38v2 權重（各約 50 MB） | Release [`research-results-models-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)，見[模型指南](<../../docs/reproducibility/MODEL_GUIDE.md>) |
| 早期共用環形訓練資料 1,100 組 | [早期主線共用環形來源](<../../Shared_Sources/Baseline_Ring_Inputs/README.md>)，有已驗證的完整還原指令 |
| stage_25／26 的 8px 序列 | 150 張乾淨影像與 150 張卷積後影像，原生成程式與主線 PSF 保留；見[四輪方法與來源](<../../docs/reproducibility/round_source_reviews/BASELINE_20261023.md>) |
| 交給公司的 ONNX 包 | [GeoEdge_COMBO_ONNX_Company_Package_20260424](<../../_deployment_package/GeoEdge_COMBO_ONNX_Company_Package_20260424/README.md>) |

> **目前的缺口與限制：**
>
> - **ONNX 模型檔還沒上雲端。** 公司包裡的 `model/geoedge_combo_body.onnx`（約 16 MB）不在 GitHub，也不在任何 Release，目前只存在原電腦上。GitHub 上這個包只有程式與說明。
> - **權重很難單獨拿。** COMBO 的訓練資料夾（權重加紀錄）只有約 172 MB，但目前的打包是按檔案大小切分卷，用 `--prefix` 取回會下載 6 個分卷、約 7.6 GB。整理計畫會處理。
> - **不能保證逐步重訓相同。** 舊的啟動程式依賴共用的 `Model/` 程式，部分歷史執行沒有完整的設定快照，GPU 設定也不固定，所以不能用今天的預設值去重現當年的訓練。見[重做限制](<../../docs/reproducibility/round_source_reviews/BASELINE_20261023.md>)。

## 原始報告

| 報告 | 什麼時候讀 |
|---|---|
| [COMBO 結果](<reports/COMBO_RESULTS.md>) | COMBO 的設計、三尺度、視覺品質與殘差 |
| [R38v2 結果](<reports/R38v2_RESULTS.md>) | R38v2 的三項修正、與 R33 的取捨，以及 R33～R38v2 每個訓練紀錄的對照表 |
| [R38v2 資料流稽核](<reports/DATA_FLOW_AUDIT.md>) | 序列資料從哪裡來、用了哪些 PSF |
| [R33～R38v2 完整系列](<../R33RobustLoss/reports/R33_R38v2_COMPLETE_EXPERIMENT_SERIES.md>) | 想一次看完 R33 到 COMBO，包括 R34／R35／R37 的失敗 |
| [英文原始說明](<README.md>) | 當時的 README，原文保留 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R38v2SeqFixed.md>)與[原結果對照](<results/SOURCE_RESULTS_GUIDE.md>)。

## 資料夾裡有什麼

| 位置 | 內容 |
|---|---|
| [reports/](<reports>) | 三份原始報告 |
| [results/](<results>) | 外部 GMF 回傳（`external_gmf/` 是 R38v2，`external_gmf_combo/` 是 COMBO）、720 角度序列分析、早期重建範例 |
| [scripts/](<scripts>) | 分析程式 |
| [MANIFEST.md](<MANIFEST.md>) | 研究保存清單 |

訓練程式在共用的 [Model/](<../../Model/README.md>)；當時的分支是 `sandbox/r38v2`。
