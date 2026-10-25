# R81：十三個模型用同一套轉折點量法比

[研究時間線](<../../docs/research/TIMELINE.md>) · [量法來源 R80](<../R80_InflectionReferenceCircleSEMValidation/FILE_GUIDE.md>) · [前一次只比兩個外部模型](<../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/FILE_GUIDE.md>) · [下一輪 R82](<../R82_R39R40CrossSceneGeneralizationBenchmark/FILE_GUIDE.md>) · [論文最後的十方法比較 R153](<../R153_MeanExternalBenchmark/FILE_GUIDE.md>)

**一句話：** 把論文的外部比較從 EDSR、NAFNet 兩個擴大到 12 個架構（從 SRCNN 到 2025 的 PFT-SR、2026 的 UCAN），全部用同一份 V42 訓練資料從頭訓練，再跟 V42 一起用 R80 的轉折點＋參考圓量法比五項指標。沒有一個模型包辦第一：20× CD 是 Restormer、50× CD 是 SwinIR、三項位移都是 UCAN；V42 沒有拿到任何一項第一，而 50× CD 原圖比所有模型都好。

| | |
|---|---|
| 結果 | **分析**（同系統受控比較，不是外部資料盲測） |
| 時間 | 2026-08-05 前後 |
| 實驗條件 | C：實驗室顯微系統；6/18 的 50×、20× 靜態九顆柱，7 月的四組位移序列 |
| 比較對象 | SRCNN、VDSR、DnCNN、Base U-Net、EDSR、RDN、RCAN、SwinIR、NAFNet、Restormer、PFT-SR 改寫版、UCAN 改寫版，以及 V42 第 120 輪 |

## 怎麼做

- **公平訓練：** 12 個外部模型都用同一份 V42 訓練包、分組切分、128 px 隨機裁切、15 輪上限與最佳驗證權重規則從頭訓練，也都接同一個固定光學輸入轉換；V42 保留它自己的量測導向訓練。
- **兩個改寫版：** PFT-SR 用官方 CUDA 核心的六層、單通道、等尺寸版本；UCAN 用官方 2026 核心的單通道、等尺寸版本。兩者都不是官方預訓練成績。
- **量法：** 只用 ACM 粗輪廓、最大梯度轉折點、LSC／MZC／MIC／MCC 參考圓；不用灰階門檻，不依模型表現重選影格。

## 結果

| 模型 | 20× CD | 50× CD | 逐步位移標準差 | 對名目步距誤差 | 九顆柱離散度 |
|---|---:|---:|---:|---:|---:|
| 原圖（參考） | 150.1 | **51.9** | 8.88 | 7.00 | 12.55 |
| SRCNN | 400.4 | 72.6 | 7.33 | 6.02 | 3.35 |
| VDSR | 282.9 | 84.3 | 7.33 | 5.96 | 4.03 |
| DnCNN | 145.4 | 86.0 | 7.57 | 5.98 | 3.81 |
| Base U-Net | 130.5 | 81.8 | 7.14 | 5.86 | 3.23 |
| EDSR | 511.4 | 68.0 | 7.20 | 5.81 | 3.76 |
| RDN | 415.7 | 86.2 | 7.37 | 6.00 | 3.53 |
| RCAN | 267.4 | 86.5 | 7.26 | 5.73 | 3.55 |
| SwinIR | 317.2 | **67.5** | 7.16 | 5.84 | 4.26 |
| NAFNet | 210.5 | 79.7 | 8.33 | 6.64 | 4.70 |
| Restormer | **114.6** | 100.2 | 7.57 | 6.12 | 3.56 |
| PFT-SR* | 479.5 | 118.5 | 7.67 | 6.18 | 4.98 |
| UCAN* | 388.9 | 82.8 | **7.03** | **5.73** | **3.06** |
| V42 | 268.3 | 100.9 | 7.29 | 5.74 | 4.89 |

（單位 nm；CD 是 LSC 直徑對 SEM 的中位絕對誤差。外部模型取自本資料夾的 `results/evaluation/<模型>/`；原圖與 V42 的數字取自 [R80](<../R80_InflectionReferenceCircleSEMValidation/FILE_GUIDE.md>)，位移欄的統計方式跟外部模型的四組合併列可能略有不同。）

## 讀這些數字要知道的事

1. **不是盲測。** 四組位移序列的所有入選影格，在 V42 訓練包裡都有對應的裁切；中心九顆柱又是 PSF 與比例尺的校正區，不是獨立樣本。
2. **「外部」指的是架構來源，不是外部資料。**
3. **平台只給名目步距**，不是獨立的干涉儀真值。
4. **五項指標分開報告**，報告明說不把它們事後平均成一個總分。
5. Wiener 只當中心九顆校正區的參考，沒有算進 13 個模型。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 12 個外部模型的逐柱 CD、逐對位移、評估設定 | 本資料夾 [results/evaluation/](<results/evaluation>)，已在 GitHub |
| UCAN 官方原始碼 | 本資料夾 `third_party/ucan_official/`，原樣保留 |
| 圖 | [results/figures/](<results/figures>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的限制：** 12 個外部模型的權重與重建影像只在原電腦上。

## 原始報告

| 文件 | 內容 |
|---|---|
| [R81 結果](<reports/R81_RESULTS.md>) | 各指標最低值、解讀界線 |
| [README](<README.md>) | 13 個模型名單、公平規則 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R81_MultiArchitectureReferenceCircleBenchmark.md>)。
