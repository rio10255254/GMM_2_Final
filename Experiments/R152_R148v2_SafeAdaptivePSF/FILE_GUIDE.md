# R152：論文採用的模型（論文中稱 MOSR）

[研究時間線](<../../docs/research/TIMELINE.md>) · [論文交接（R153）](<../R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md>) · [上一輪 R151](<../R151_R148v2_AdaptivePSFFusion/README.md>) · [底座 R148v2](<../R148v2_HybridContextNativePSF/README.md>)

**一句話：** 把論文架構需要的「多顆 PSF 頻域加權融合」模組接到已經表現良好的 R148v2 上，同時不破壞 R148v2 的量測表現。在 930 張實拍上，單趟 30 步的位移波動從 RAW 的 8.781 nm 降到 4.273 nm（−51.3%，論文口徑），30 趟全部改善。

> **兩種位移口徑：** 論文採用的是九顆柱體位移的**算術平均**（回應口試委員建議，由 [R153](<../R153_MeanExternalBenchmark/reports/MEAN_MEDIAN_RESULTS.md>) 重算），RAW 8.781 → 4.273 nm。本頁下方的結果表與本資料夾的原始報告用的是當時的**中位數**口徑，RAW 10.200 → 4.865 nm（−52.3%），論文不再沿用。只有位移類數字受影響，直徑、輪廓與 SEM 的數字兩者相同。

| | |
|---|---|
| 結果 | **採用**（論文採用模型）；沒有取代公司端的正式基準 COMBO |
| 時間 | 2026-09-28 訓練完成，09-29 完成 930 張實拍驗證 |
| 實驗條件 | D：均華 20× 物鏡 + PI 平台，2026-09-03 拍攝的 30 趟 × 31 位置 |
| 起點 | 凍結的 R148v2 第 8,192 次權重 |

## 在研究裡的位置

到 9 月底，R141～R147 試過各種把實測 PSF 放進訓練與模型的方法，多半讓短步或輪廓退步。R148v2 改用「一次多尺度脈絡加三段原尺寸邊界修正」，第一次在 930 張上站穩，但它沒有論文架構裡的多 PSF 融合模組。R151 試過把可學習的 PSF 融合放回去，機制能跑，可是 25 顆 PSF 太相似，網路分辨不出來。

R152 的做法因此很保守：**R148v2 一個權重都不動**，只在它的輸出後面接一條很弱的 PSF 修正支路，讓論文需要的模組確實存在、確實參與計算，但不冒險破壞已經驗證過的表現。

## 這輪在問什麼

能不能把「FFT → 多顆 PSF → 權重估計 → 加權融合 → 受限殘差比例 → 原圖連接」補回模型，同時把 R148v2 的位移、直徑與輪廓表現保住？

事先寫定的完成條件是：**模組有載入、有接受訓練、有參與輸出就算完成**。刻意不要求網路能正確辨認是哪一顆 PSF。

## 怎麼做

```text
輸入影像 x ──> 凍結的 R148v2 ──────────────────────────> y_base
       ├─> 頻率統計 ─┐
       ├─> FFT ──────┼─> 25 顆 PSF 的加權受限反濾波 ─> iFFT ─> 很弱的修正
       └─> U-Net 脈絡┘                                        │
                                                              └─> 加到 y_base ─> R152 輸出
```

- **凍結：** R148v2 的 1,194,406 個參數全部凍結；只訓練新增的 12,699 個參數。
- **刻意很弱：** 兩個比例相乘約 0.000165，理論上單像素最多只改約 0.011 灰階。交付倍率設成 0，就跟 R148v2 逐像素相同。
- **事先選倍率：** 在合成開發集上比較倍率 0、0.25、0.5、0.75、1，每一項都不能比原版差超過 0.5%，選整體最好的那個（1.0）。**實拍結果沒有被拿來回頭挑倍率。**
- **訓練：** 8,192 次更新，FP32、關閉 TF32、RTX A6000；資料沿用 R148v2 的 768 個合成母場景（3,072 個視圖）。

完整架構與每個超參數見[模型架構與完整實驗紀錄](<reports/R152_COMPLETE_MODEL_AND_EXPERIMENT_RECORD_20260929.md>)第 2、4 節。

## 結果

930 張、8,370 顆圓，所有方法用同一套量測程式（主動輪廓粗定位、法線方向取邊、最小平方法擬圓）。單位 nm，越小越好。**下表是 R152 原紀錄的中位數口徑**；論文用的平均口徑見頁首與 [R153](<../R153_MeanExternalBenchmark/FILE_GUIDE.md>)。

| 指標 | RAW | R148v2 | **R152** |
|---|---:|---:|---:|
| 單趟 30 步波動（合併標準差，主要指標） | 10.200 | 4.865 | **4.865** |
| 短步相對 PI 平均絕對差 | 8.167 | 4.003 | 4.003 |
| 起點相對長距離平均絕對差 | 19.081 | 18.002 | 18.002 |
| 直徑重拍波動 | 32.750 | 13.252 | 13.252 |
| 輪廓重拍波動 | 63.758 | 18.600 | 18.600 |
| 與 SEM 表的平均直徑差 | **169.883** | 204.281 | 204.281 |

- 對 RAW 的單趟波動，**30／30 趟都改善**，逐趟改善 36.9%～64.6%，合併改善 52.3%（以整趟重抽樣的 95% 區間 49.6%～55.1%）。排除曾用來校準方向的前 6 趟，後 24 趟也全部改善。
- 25 顆 PSF 的權重幾乎均分（每顆約 0.040，均分是 0.04）。
- 推論約慢 2.2%，顯示卡記憶體多約 0.34 GiB。

## 讀這些數字要知道的事

這幾句是結論的一部分，引用時請一起帶上：

1. **改善幾乎全部來自底座 R148v2。** R152 和 R148v2 的差距只有百萬分之一奈米的等級，沒有實際量測意義。論文採用 R152，是因為它補回了論文架構需要的模組，同時保住了表現，**不是**因為這個模組帶來改善。
2. **更穩不等於更準。** 與 SEM 的平均直徑差反而比 RAW 大約 34 nm。
3. **SEM 不是完全獨立的驗證。** 同一批實物的 SEM 外框曾參與 PSF 校準，所以 SEM 比較只算校準條件下的一致性檢查。
4. **沒有證明能辨認 PSF。** 權重近乎均分，也只在三張影像上檢查過權重。
5. **不是每一欄都變好。** 最差直徑偏移微增 0.000053 nm，速度和記憶體也有成本。
6. **論文用的是平均口徑。** 本頁結果表的 RAW 10.200 nm 是九顆圓取中位數；R153 改用九顆算術平均重算後，RAW 是 8.781 nm、MOSR 是 4.273 nm。R153 的報告明寫論文應使用新數字，不得沿用中位數版本的 52.3%。兩種口徑不能混在同一張表裡比較。

## 拿資料與重做

只想看數字的話，不需要下載任何東西：[完整紀錄](<reports/R152_COMPLETE_MODEL_AND_EXPERIMENT_RECORD_20260929.md>)第 6～9 節有全部結果表，[單趟 30 步逐趟數值](<reports/R152_SINGLE_SCAN_STEP_SD_20260930.md>)有 30 趟逐筆數據。

> **原始結果檔在哪裡：** 完整紀錄第 11 節引用的 `results/`（位移、尺寸、SEM、配對區間等比較表，930 張的圓心與輪廓，完成標記）和 `runs/formal_8192/`（訓練紀錄與倍率選擇）不在 GitHub 程式樹裡，所以那些連結在 GitHub 上點不開。它們已經保存在 Release [`research-results-models-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)，內容與原檔逐位元組相同。
>
> 但目前的打包是按檔案大小切分卷，不是按輪次：只要 R152 的結果（約 430 MB），也得下載 14 個分卷、約 20 GB。這是現在保存方式的限制，整理計畫會處理。

| 需要什麼 | 在哪裡 |
|---|---|
| R152 部署模型、凍結的 R148v2、25 顆 PSF 與設定 | Release [`research-training-kits-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-training-kits-20261016) 的 `research-r152-frozen-inputs-001.zip`（約 28.8 MB），解開後放在 [R152 生成包](<../../Deliverables/R152_Standalone_ImageFiles_20261004/README.md>) 的 `weights/` 與 `calibration/`；內容與用途見[模型指南](<../../docs/reproducibility/MODEL_GUIDE.md>) |
| 930 張原始照片與 30 份平台紀錄 | Release [`shared-pi-20260903-v1`](https://github.com/rio10255254/GMM_2_Final/releases/tag/shared-pi-20260903-v1)，還原方法見 [PI 原始拍攝資料](<../../Shared_Sources/PI_Repeatability_20260903/README.md>) |
| 全部 9,216 張訓練 TIFF | 不上傳，用固定種子重新生成，逐張核對原版像素：[生成包](<../../Deliverables/R152_Standalone_ImageFiles_20261004/README.md>) |
| 訓練與推論程式 | [獨立包](<../../Deliverables/R152_Standalone_ImageFiles_20261004/README.md>)（`train.py`、`infer.py`、`settings.py`），或本資料夾的原始程式 |

下載模型附件：

```powershell
gh release download research-training-kits-20261016 --repo rio10255254/GMM_2_Final --pattern research-r152-frozen-inputs-001.zip --dir downloads
```

重新生成訓練資料（需要 numpy、scipy、Pillow，並先備妥 25 顆 PSF 的 `calibration/psf25_bank.npz`）：

```powershell
cd Deliverables/R152_Standalone_ImageFiles_20261004
python generate_data.py --output-dir outputs/generated_data --workers 2
```

在本資料夾執行 `python scripts/verify_complete_record.py`，可以唯讀核對完整紀錄裡的關鍵數字與 26 個資料連結。

**重做的範圍：** 訓練資料已從固定種子完整重新生成並與原版逐像素相同；正式的 8,192 次訓練**沒有**重跑。

**關於模型檔的身分：** 上面那包裡的部署模型（`r152_deployed.pth`，SHA-256 開頭 `2932f79d`）是把原權重容器裡的舊電腦路徑移除後重新存檔的，所以跟完整紀錄裡實拍驗證用的保存點（開頭 `17bf7c63`）雜湊不同；但 209 個權重張量逐一相同，真實示例影像的推論輸出也逐像素相同，見[獨立包報告](<reports/R152_STANDALONE_PACKAGE_20261004.md>)。`17bf7c63` 這個原檔本身不在任何 Release 裡，目前只在原電腦的 `runs/formal_8192/checkpoints/deployed_step08192.pth`（約 7.1 MB），整理計畫會優先補上；第 8,192 次訓練完成時的保存點（開頭 `dc9e0b1d`）則在 [`research-results-models-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016) 的 `research-fixed-models-020.zip`。

## 原始報告

| 報告 | 什麼時候讀 |
|---|---|
| [模型架構與完整實驗紀錄](<reports/R152_COMPLETE_MODEL_AND_EXPERIMENT_RECORD_20260929.md>) | 想看完整設計、每個數字與可寫／不可寫的主張 |
| [RAW 與 R152 完整研究紀錄](<reports/R152_RAW_FULL_RECORD_20261002/REPORT.md>) | 寫論文時；用目前確認的單趟 30 步定義全部重算，附逐筆數據與灰階圖 |
| [單趟 30 步波動](<reports/R152_SINGLE_SCAN_STEP_SD_20260930.md>) | 想看 30 趟逐趟的改善 |
| [設計與前測](<reports/R152_DESIGN_AND_PREFLIGHT.md>) | 想知道訓練前怎麼定規則 |
| [訓練結果](<reports/R152_TRAINING_RESULTS.md>)、[完整實拍驗證](<reports/R152_FULL_REAL_VALIDATION.md>) | 分段的原始紀錄 |
| [論文圖像補件](<reports/R152_THESIS_VISUAL_EVIDENCE_20261003/FIGURE_NOTES.md>) | 25 顆 PSF、RAW／MOSR 同視野、30 條實測輪廓與圖說 |
| [獨立包](<reports/R152_STANDALONE_PACKAGE_20261004.md>)、[TIFF 訓練包](<reports/R152_TIFF_TRAINING_PACKAGE_20261004.md>)、[資料重新生成核對](<reports/R152_DATA_GENERATION_REPRODUCTION_20261004.md>) | 想搬到別台機器訓練或推論 |
| [英文原始說明](<README.md>) | 當時的 README，原文保留 |

其餘報告在 [reports/](<reports/README.md>)。2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R152_R148v2_SafeAdaptivePSF.md>)。

## 資料夾裡有什麼

| 位置 | 內容 |
|---|---|
| [model.py](<model.py>)、[base_model.py](<base_model.py>) | R152 主體；凍結的 R148v2 主體複本 |
| [optical/](<optical>) | 新增的頻域 PSF 融合模組 |
| [calibration/](<calibration>) | 25 顆 PSF 銀行與來源鎖（`measured_psf_bank.npz` 約 0.7 MB，已在 GitHub） |
| [config/](<config/README.md>) | 模型、訓練、資料設定 |
| [train.py](<train.py>)、[dataset.py](<dataset.py>)、[losses.py](<losses.py>)、[utils.py](<utils.py>) | 訓練程式 |
| [scripts/](<scripts/README.md>) | 實拍重建、量測、比較、稽核與核對工具 |
| [results/](<results/README.md>) | 930 張的量測、比較表、速度、分塊一致性與最終稽核 |
| [reports/](<reports/README.md>) | 原始報告 |
| [MANIFEST.md](<MANIFEST.md>) | 研究保存清單 |

模型權重和訓練影像不在 GitHub 程式樹裡，見上面「拿資料與重做」。
