# R153：論文的十方法比較，以及九顆平均的新口徑

[研究時間線](<../../docs/research/TIMELINE.md>) · [被比較的論文模型 R152（MOSR）](<../R152_R148v2_SafeAdaptivePSF/FILE_GUIDE.md>) · [論文交接](<reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md>) · [論文修改指南](<reports/FINAL_BENCHMARK_THESIS_HANDOFF/PAPER_UPDATE_GUIDE.md>)

**一句話：** R153 做了兩件事。第一，回應口試委員的建議，把九顆柱體的位移從「取中位數」改成「取算術平均」重新計算，這成為論文的新口徑（RAW 8.781 → MOSR 4.273 nm，−51.3%）。第二，在同一批 930 張實拍上，把 MOSR 跟 RAW、Wiener 以及七個從零訓練的外部網路（EDSR、NAFNet、RDN、RCAN、Restormer、USRNet、SwinIR）完整比較，並在同一張 GPU 上測效率。MOSR 在三個主要位移與輪廓指標上都是這批資料的最低點估計；U-Net 和 MambaIRv2 因為官方後端無法執行，沒有完成，也沒有用替代網路填數字。

| | |
|---|---|
| 結果 | **分析**（不重新訓練 MOSR，不改 MOSR 的架構、權重、既有圓心與輪廓） |
| 時間 | 2026-10-05 完成平均口徑重算；10-06 九方法交付；10-07 補完 SwinIR，十方法交付 |
| 實驗條件 | D：均華 20× 物鏡 + PI 平台，2026-09-03 拍攝的 30 趟 × 31 位置 |
| 規模 | 每個方法 930 張、8,370 個讀值、30 趟全部有效、零失敗；150 次效率量測、162 組整趟配對區間 |

## 在研究裡的位置

R152 完成後成為論文採用的模型。論文口試時，委員對九顆柱體位移的彙整方式提出建議，R153 先處理這件事；接著補上論文需要的「跟其他重建方法比較」，讓 MOSR 的結果有參照。

## 這輪在問什麼

1. 改用九顆位移向量的算術平均之後，R152 對 RAW 的結論還成立嗎？
2. 在相同資料、相同量測規則下，MOSR 跟常見的影像重建網路相比如何？
3. 效率上的代價是多少？

## 怎麼做

**平均口徑：** 每一步先把九顆柱體的二維位移向量取算術平均，再投影到固定的移動方向（尺度 172.5 nm/像素）。舊的中位數版本作為敏感度比較保留。原中位數的 3,600 筆位移全部重現，最大差 3.55×10⁻¹⁵ µm，所以兩者的差別只來自彙整方式。

**外部方法：** 都用跟 MOSR 相同的合成資料（768 個母場景：512 訓練、128 驗證、128 測試），各自用作者常用的目標函數從零訓練；設定和權重只依合成驗證選擇，實拍、PI、SEM 都沒有參與。實拍量測沿用 MOSR 那套固定讀法，沒有後置銳化、尺寸修正或重新配準。

**效率：** 同一張 RTX A6000、FP32、batch=1、TF32 關閉，固定三張 1544×2064 實拍（第 0、465、929 張），各暖身兩次、正式前向五次，每個方法用獨立的新程序。

## 結果

**主要指標**（平均口徑，單位 nm，越小越好）：

| 方法 | 單趟 30 步合併波動 | 相鄰步相對 PI 平均絕對差 | 輪廓重拍波動 | 直徑重拍波動 | 與 SEM 的直徑差 | 訓練 |
|---|---:|---:|---:|---:|---:|---|
| RAW | 8.781 | 6.969 | 63.758 | 32.750 | **169.883** | — |
| Wiener | 5.953 | 4.793 | 27.885 | 27.478 | 170.693 | 無 |
| EDSR-x1 | 4.772 | 3.992 | 18.860 | 21.405 | 202.088 | 32 輪 |
| NAFNet | 4.747 | 3.919 | 21.810 | 30.987 | 230.512 | 32 輪 |
| RDN-x1 | 4.975 | 4.147 | 19.488 | 16.928 | 190.509 | 14 輪 |
| RCAN-x1 | 5.206 | 4.346 | 24.058 | 26.479 | 204.671 | 8 輪 |
| Restormer | 5.666 | 4.716 | 20.723 | 24.302 | 172.840 | 8 輪 |
| USRNet-x1 | 5.024 | 4.070 | 22.887 | 15.748 | 213.302 | 8 輪 |
| SwinIR | 5.100 | 4.272 | 27.494 | 16.561 | 201.159 | 8 輪 |
| **MOSR** | **4.273** | **3.598** | **18.600** | **13.252** | 204.281 | 8,192＋8,192 次更新 |

**整趟配對比較**（MOSR 減各方法，以 30 趟為單位重抽樣 20,000 次）：除了「對 EDSR-x1 的輪廓重拍波動」區間跨零、差異尚未確定之外，其他每一項的 95% 區間都落在 MOSR 較低的一側。MOSR 的單趟波動在 30 趟中比 RAW、Wiener、Restormer、SwinIR 每一趟都低；比 EDSR 低 25 趟、比 NAFNet 低 24 趟。

**效率**（暖身後的平均前向時間，秒；GPU 配置峰值，GiB）：

| 方法 | 秒 | 配置峰值 | 保留峰值 |
|---|---:|---:|---:|
| NAFNet | 0.513 | 3.12 | 4.34 |
| EDSR-x1 | 0.526 | 3.06 | 3.10 |
| **MOSR** | 1.461 | 2.79 | 5.56 |
| USRNet-x1 | 2.967 | 4.66 | 5.34 |
| Restormer | 5.007 | 26.97 | 36.34 |
| RCAN-x1 | 6.731 | 3.87 | 3.91 |
| RDN-x1 | 9.873 | 32.71 | 41.50 |
| SwinIR | 27.171 | 31.39 | 31.48 |

MOSR 沒有比 EDSR、NAFNet 快；它的配置峰值最低，但保留峰值比 EDSR、NAFNet 高，所以不能寫成「所有記憶體占用都較低」。

## 讀這些數字要知道的事

這些句子是交接文件要求引用時一起保留的：

1. **論文要用平均口徑的新數字。** 不得沿用中位數版本的 52.3% 步距改善與 51.0% 相鄰 PI 改善。直徑、輪廓、SEM 不受彙整方式影響。
2. **訓練輪數不相等。** EDSR 與 NAFNet 32 輪；RDN 14 個完整輪（另有第 15 輪 128 次未完成的更新，沒有採用）；RCAN、Restormer、USRNet、SwinIR 各 8 輪。這是為了縮短等待而由專案負責人指定的較短訓練比較，**不能宣稱各模型都已充分收斂或用了相同訓練時間**。
3. **點估計排名不等於普遍結論。** MOSR 在三個主要欄位是「本批資料的最低點估計」；多個比較沒有做家族錯誤校正，也只有單一樣品、單一時段。
4. **更穩不等於更準。** 與 SEM 的直徑差，RAW、Wiener、Restormer 都比 MOSR 小；而 SEM 曾參與 PSF 校準，只算相同校正條件下的參照，不是獨立的絕對真值。
5. **速度不能推論量測效果。** 效率是三張固定影像的穩態前向時間，不含讀檔與傳輸，也不是開機到第一張的等待時間。
6. **不能歸因到單一模組。** 這是固定資料與量測規則下的整體方法比較，架構、目標函數和輪數都不同，不能由這張表推論某個 PSF 模組或損失項的因果效果。
7. **兩個沒完成的方法。** U-Net 的官方版本需要 Caffe 的 Linux 後端；MambaIRv2 的官方 CUDA 程式在本機編譯失敗（C2975 模板常數錯誤）。本機也沒有可用的 WSL 或 Docker Linux 後端。兩者都沒有用簡化網路代替，錯誤紀錄與來源完整保留。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 十方法交接（報告、灰階圖、全部 CSV） | [reports/FINAL_BENCHMARK_THESIS_HANDOFF/](<reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md>)，已在 GitHub |
| 平均與中位數的完整比較 | [MEAN_MEDIAN_RESULTS.md](<reports/MEAN_MEDIAN_RESULTS.md>)；平均口徑的論文資料包在 [MOSR_MEAN_THESIS_HANDOFF_20261005/](<reports/MOSR_MEAN_THESIS_HANDOFF_20261005/MOSR_MEAN_THESIS_HANDOFF.md>) |
| 論文要改哪裡 | [論文修改對照表](<reports/THESIS_UPDATE_MAP.md>)、[修改指南](<reports/FINAL_BENCHMARK_THESIS_HANDOFF/PAPER_UPDATE_GUIDE.md>) |
| 外部模型權重、訓練紀錄（約 2.9 GB） | Release [`research-results-models-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)，目前要下載約 23 GB |
| 外部模型的作者原始碼 | 本資料夾 [vendor/](<vendor>)；精確來源版本與訓練設定記在 [config/](<config>) |
| 共用訓練資料 | [R152 生成包](<../../Deliverables/R152_Standalone_ImageFiles_20261004/README.md>) 的 TIFF 資料，可用固定種子重新產生 |
| 交付核對 | `python Experiments/R153_MeanExternalBenchmark/scripts/verify_final_delivery.py`（不做 GPU 重建或重新擬合） |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **補充：** 原始說明提到的兩個 zip（`FINAL_BENCHMARK_THESIS_HANDOFF.zip`、`MOSR_MEAN_THESIS_HANDOFF_20261005.zip`）只在原電腦上，但它們的內容已經以資料夾形式在 GitHub 上，所以不影響閱讀與取用。外部模型的 930 張重建輸出依保存原則留在原電腦，沒有上傳。

## 原始報告

| 報告 | 什麼時候讀 |
|---|---|
| [十方法論文交接](<reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md>) | 最完整的一份：效率、實拍結果、尺寸與長距離、配對區間、SEM 輪廓、計算公式、各模型設定、MOSR 完整架構、失敗紀錄 |
| [平均與中位數比較](<reports/MEAN_MEDIAN_RESULTS.md>) | 為什麼論文改用平均、新舊數字差多少 |
| [論文修改對照表](<reports/THESIS_UPDATE_MAP.md>) | 對照論文頁碼的修改清單 |
| [基準結果](<reports/BENCHMARK_RESULTS.md>)、[最終結果](<reports/FINAL_BENCHMARK_RESULTS.md>)、[最終效率](<reports/FINAL_BENCHMARK_EFFICIENCY.md>) | 分項的原始紀錄 |
| 七方法、九方法的階段性交接 | [AVAILABLE_MODELS_STAGE_COMPLETE/](<reports/AVAILABLE_MODELS_STAGE_COMPLETE>)、[COMPLETED_MODELS_THESIS_HANDOFF/](<reports/COMPLETED_MODELS_THESIS_HANDOFF>)；歷史版本，原樣保留 |
| [重做稽核](<reports/R153_REPRODUCTION_AUDIT_20261016.md>) | 2026-10-16 的保存核對 |
| [原始說明](<README.md>) | 任務定義與每一階段的執行紀錄，原文保留 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R153_MeanExternalBenchmark.md>)。當時的分支是 `sandbox/r153-mean-external-benchmark`。

## 資料夾裡有什麼

| 位置 | 內容 |
|---|---|
| `benchmark_core.py`、`benchmark_models.py`、`inference_methods.py`、`normal_*.py`、`study.py` | 比較框架、模型定義、推論與訓練 |
| [vendor/](<vendor>) | 外部模型的作者原始碼 |
| [config/](<config>) | 來源鎖、時間上限、使用者授權紀錄 |
| [evaluation/](<evaluation>) | 固定量測讀法 |
| [scripts/](<scripts>) | 訓練、驗證、效率、彙整、交付與核對 |
| [reports/](<reports/README.md>) | 全部報告與交接包 |
| [results/](<results>)、[runs/](<runs>) | 結果與執行紀錄（大型部分在 Release） |
| [MANIFEST.md](<MANIFEST.md>) | 研究保存清單 |
