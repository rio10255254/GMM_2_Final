# R61 STEP：v16 在 Step 樣品上的驗證入口

[研究時間線](<../../docs/research/TIMELINE.md>) · [模型本體 Lab R61](<../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/FILE_GUIDE.md>) · [Step 分析資料夾](<../../Step_analysis_20260623/_curated_final_20260624/README_STEP_VALIDATION.md>) · [論文證據入口](<../../Thesis_MOSR_Evidence/Experiments/20260624_STEP_boundary_displacement_cd_validation/README_THESIS_ENTRY.md>)

**一句話：** 這個資料夾不是另一份從零訓練的 R61，而是把 Lab R61 在 2026-06-23 的幾次模擬幻影驗證從專案根目錄搬過來集中保存，並當作 v16 在 Step 樣品上驗證的入口。Step 樣品上，v16 讓外部 GMF 的步距更穩（1 µm 步距的標準差從 0.191 降到 0.129 px），100、200 µm 圓的直徑比原圖更接近標稱值約 0.17 µm，量測對門檻的敏感度也從 ±0.33 µm 降到 ±0.03 µm。

| | |
|---|---|
| 結果 | **研究候選**（v16 在 Step 上支持 CD 保留與位移穩定；不能證明跨樣品通用；之後的 SEM 來源審查限制了獨立準確度宣稱） |
| 時間 | 2026-06-23 模擬幻影驗證；06-24 Step 樣品驗證；07-02 用校正報告重新核對 |
| 實驗條件 | B：實拍 Step 樣品（20×，0.125 µm/px），連續 1 µm 與 0.5 µm 位移序列；校正參考是 Step 樣品的校正報告 |
| 模型 | Lab R61 v16（`stepguard_v16`） |

正式基準仍然是 COMBO（r38v2_8px_gate_p95）；R61 沒有升為正式基準。

## 這輪在問什麼

Lab R61 的 v16 在模擬幻影上沒過自己的三道門檻，但在 Step 這種有校正尺寸的實拍樣品上，它能不能保住位移和尺寸？

## 怎麼做

1. **模擬幻影：** `runs/` 裡六次驗證是 R61 不同版本（motion-v11、motion-gradient、motion-texture、v16 等）在同一組 96 個案例上的邊界比較，每次附一份當時的推論程式副本。
2. **Step 外部 GMF：** 從 Step 影像中心 2048 的方塊區域送外部 GMF，只做了 Raw 和 v16 各一組（rep0）。
3. **Step CD：** 擬合同心圓的 100、200、300、500 µm 圓直徑，40 張的平均，跟標稱值比，並掃描門檻看敏感度。

## 結果

**模擬幻影（v16 對 R61 內部的 R39 a970、R8，以及 v14）：** 平均、第 95 百分位、最大邊界誤差都持平或略好，但 0 與 0.5 px 小偏移組比內部 R39 a970 差，所以三組比較都判為未過。

**Step 外部 GMF（中心方塊，X 方向）：**

| 序列 | 影像 | 步距中位數 | 步距標準差 | 絕對誤差中位數 | 平均分數 |
|---|---|---:|---:|---:|---:|
| 1 µm（預期 8 px） | 原圖 | 7.995 px | 0.191 px | 0.021 µm | 94.6 |
| 1 µm | v16 | 8.050 px | **0.129 px** | **0.013 µm** | 99.8 |
| 0.5 µm（預期 4 px） | 原圖 | 4.030 px | 0.198 px | 0.016 µm | 94.7 |
| 0.5 µm | v16 | 4.007 px | **0.143 px** | **0.011 µm** | 99.8 |

**Step CD（中心區域，40 張平均）：**

| 標稱直徑 | 原圖 | 原圖誤差 | v16 | v16 誤差 | 門檻敏感度（原圖／v16） |
|---:|---:|---:|---:|---:|---|
| 100 µm | 99.288 | −0.712 | 99.462 | −0.538 | ±0.329／±0.026 µm |
| 200 µm | 199.519 | −0.481 | 199.692 | −0.308 | ±0.337／±0.026 µm |

## 讀這些數字要知道的事

1. **校正報告不是直徑表。** 拍照取得的那頁是圓度（形狀偏差）頁，只確認了標稱尺寸；7/2 補來的第 3 頁是 EUV 圖樣的實測尺寸修正，不適用於這裡量的同心圓。所以 CD 是跟**標稱值**比，不是跟認證值比。
2. **GMF 只有一組重複。** Raw 和 v16 各只有 rep0，且第一張都沒被計分。
3. **v14、內部 R39 a970 的 CD 跟 v16 幾乎一樣**（100 µm 都約 99.46 µm），所以 CD 的改善不是 v16 特有，而是這個模型家族共有。
4. **不能混用 100MG 的 SEM 證據。** README 的守則寫明，Step 的結果只能綁在 Step 樣品上。
5. 這裡的 R39、R8 是 Lab R61 內部試跑的序號，不是主專案或 Lab 的 R39；說明見 [Lab R61](<../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/FILE_GUIDE.md>)。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 模擬幻影門檻摘要與推論程式副本 | 本資料夾 [runs/](<runs>)，已在 GitHub |
| Step 挑選、外部 GMF、CD 與形狀、來源路徑 | [Step 分析整理版](<../../Step_analysis_20260623/_curated_final_20260624/README_STEP_VALIDATION.md>)，已在 GitHub |
| 7/2 的 CD 與圓度重新核對 | [CD 重新核對](<../../Step_analysis_20260623/cd_calibration_report_recheck_20260702/STEP_CD_RECHECK_READOUT.md>)、[圓度重新核對](<../../Step_analysis_20260623/cd_calibration_report_recheck_20260702/STEP_ROUNDNESS_RECHECK_READOUT.md>) |
| v16 模型與 ONNX | 見 [Lab R61](<../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/FILE_GUIDE.md>) 的「拿資料與重做」 |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的限制：** README 提到的 `R61_RUN_INDEX.csv`、`R61_MOVE_MANIFEST.csv`、`R61_FILE_INVENTORY.csv` 不在 GitHub 程式樹上，在 Release [`research-results-models-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016) 的壓縮包裡；Step 原始影像、重建影像與 GMF 打包資料只在原電腦或外接硬碟上。

## 原始報告

| 文件 | 內容 |
|---|---|
| [README](<README.md>) | 這個資料夾的兩個角色、關鍵 run、守則 |
| [v16 邊界門檻摘要](<runs/R61_stepguard_v16_dpv96_matched_20260623/diverse_phantom_validation_20260623_220416/BOUNDARY_GATE_SUMMARY.md>) | v16 對內部 R39 a970、R8、v14 的 96 案例比較 |
| [論文證據入口](<../../Thesis_MOSR_Evidence/Experiments/20260624_STEP_boundary_displacement_cd_validation/README_THESIS_ENTRY.md>) | 可以說什麼、不該誇大什麼 |
| [MANIFEST](<MANIFEST.md>) | 2026-10-16 補建的保存清單 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R61_STEP_Generalization_20260623.md>)。
