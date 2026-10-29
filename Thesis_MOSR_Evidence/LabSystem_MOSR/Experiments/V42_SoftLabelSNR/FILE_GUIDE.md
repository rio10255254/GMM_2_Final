# V42：R152 之前的論文模型

[研究時間線](<../../../../docs/research/TIMELINE.md>) · [LabSystem 全線](<../../../../docs/reproducibility/lineage/LAB_SYSTEM.md>) · [V41](<../V41_Standalone/FILE_GUIDE.md>) · [Lab R61](<../R61_BoundaryGeneralizationUniversal/FILE_GUIDE.md>) · [取代它的 R152](<../../../../Experiments/R152_R148v2_SafeAdaptivePSF/FILE_GUIDE.md>) · [V42 完整歷史](<../../../../docs/reproducibility/lab_comparisons/V42_HISTORY.md>)

**一句話：** 從 V41 出發，把答案影像的邊緣帶柔化，避免答案本身有像素階梯；再加入一個依影像品質調整反應的分支，只更新少數幾個部分，完整訓練 120 輪。2026 年 7 月到 9 月，論文用的 MOSR 就是 V42：在 6/18 的 50× 靜態影像上，九顆柱體的 CD 比 RAW 更接近 SEM；在 7 月的四組 30 步位移序列上，四組合併的步距誤差下降約 29%。9 月底由 R152 取代。

| | |
|---|---|
| 結果 | **採用**（2026-07～09 的論文模型；之後由 R152 取代） |
| 時間 | 2026-07-09 短測與完整包建立；同日開始 120 輪完整訓練 |
| 實驗條件 | C：實驗室顯微系統（LabSystem）的資料與 PSF；論文結果用 6/18 的 50× 靜態影像，以及 7 月的 50×、20× 位移序列 |
| 起點 | V41 完整訓練的最佳保存點（第 16 輪）；V41 又從 Lab R61 v16 起步 |

這是 LabSystem 的 V42，跟主專案的 R42 是兩件不同的事。

> **閱讀提醒：** 論文證據區的 [`01_CURRENT_THESIS_RESULTS_V42_CENTER9/`](<../../../Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/README.md>) 寫著「這是目前論文應引用的結果入口」，那是 2026 年 7 月的狀態，資料夾名稱沒有改。現在論文採用的是 R152 對 RAW 的 930 張比較，見 [R153 論文交接](<../../../../Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md>)。

## 在研究裡的位置

LabSystem 從 6 月開始，一路修角點、模糊來源、答案風格，到 R57～R60 改用 SEM 尺寸當答案，再到 R61 擴大通用邊界與位移保護（v16）、R62 針對目標樣品增補。V41 從 R61 v16 起步，用 R62 那批 11,254 組資料完整訓練；V42 再針對兩個懷疑的邊界問題做修正。

之後主專案的 R111（R109 能不能取代 V42）、R128（v34 名單補測）都評估過取代 V42，結論都是暫不替換。9/18～9/20 曾規劃把論文改成只用 [R129](<../../../../Experiments/R129_OpticalPriorHybrid/FILE_GUIDE.md>)（留下改寫計畫與備稿資料）；最後是 9 月底的 R152 正式取代。

## 這輪在問什麼

V41 有兩個懷疑的問題：答案影像的邊界可能有像素階梯；模型對影像品質（訊雜比）沒有明確的反應機制。把答案的邊緣帶柔化、再加一個品質閘，能不能改善邊界忠實度？

## 怎麼做

- **柔化答案：** 原圖不動，只在答案影像窄窄的邊緣帶內做高斯平滑。完整資料仍是 11,254 組、15 類，其中 180 組的答案被柔化（是在原位置替換，不是再加 180 組）。
- **品質閘：** 模型新增一個可開關的 `quality_gate` 分支，預設關閉，所以舊 V41 的行為不變。
- **只更新少數部分：** 完整訓練只允許 `quality_gate`、`boundary_adapter`、`p1`、`out` 更新，並以 V41 當區域老師；不是整個主幹從零重訓。V41 起點與第 120 輪共有 135 份權重陣列，其中 112 份完全相同。

## 結果

以下是 2026 年 7 月論文用的結果（中心九顆柱體 P22、P23、P24、P28、P29、P30、P34、P35、P36；模型用第 120 輪）：

**CD**（6/18 的 50× 靜態影像，對照 SEM）：

| 影像 | 九顆平均絕對誤差 | 九顆最大絕對誤差 |
|---|---:|---:|
| RAW | 92.99 nm | 129.11 nm |
| V42 第 120 輪 | 78.18 nm | 113.85 nm |

九顆在 V42 中都比 RAW 更接近 SEM，但仍然全部偏大。

**位移**（每組固定 30 步，只依 RAW 的運動偏差挑選，不用 V42 的結果挑）：

| 序列 | RAW 波動 | V42 波動 | 降低 |
|---|---:|---:|---:|
| 50×、0.5 µm | 7.04 nm | 3.61 nm | 48.7% |
| 50×、1.0 µm | 7.69 nm | 3.72 nm | 51.6% |
| 20×、0.5 µm | 16.25 nm | 14.73 nm | 9.4% |
| 20×、1.0 µm | 13.52 nm | 6.94 nm | 48.7% |

四組合併 120 步：對指令值的平均絕對偏差從 9.54 nm 降到 6.74 nm（−29.4%），九顆之間的不一致從 17.63 nm 降到 6.47 nm（−63.3%），120 步中 107 步改善。同一包裡的 Wiener 反卷積基準是 7.46 nm 與 7.92 nm。

## 讀這些數字要知道的事

1. **「V42」不是單一個檔案。** 兩輪短測、120 輪完整訓練、第 10 輪的平滑保存點、第 120 輪的權重，各有各的身分：
   - 完整包根目錄的預設 `weights/best_tradeoff` 是**第 2 輪的短測模型**，不能拿它代替完整訓練；
   - 完整訓練資料夾內的 `best_tradeoff` 是第 10 輪的平滑（EMA）狀態；
   - `epoch_010` 是第 10 輪當下的網路狀態，有 26 份陣列跟上一項不同；
   - 7 月論文比較用的是**第 120 輪**。
2. **原始訓練表有欄位錯置。** 表頭 177 欄，寫入程式每輪實際寫 169 個值，有兩處方向相反的錯位：照原欄名直接讀，會把 PSNR 15.44 當成 SSIM。修正欄名後的另存表不改任何數值；原表、錯誤表頭與原寫入程式都保留。
3. **不是獨立未知樣本的驗證。** V42 的資料繼承了 SEM／實體邊界、目標樣品與老師答案；CD 結果只適用於 6/18 那張 50× 影像與這九顆已知 SEM 的柱體。
4. **20×、0.5 µm 那組只改善 9.4%**，比其他三組弱得多。
5. **跟現在的論文數字不能直接比。** 這裡用的是 6～7 月的資料與 30 步挑選規則；R152 用的是 9/3 的 930 張、30 趟完整資料與不同的讀法。
6. **8 月底的結構拆解（[R113](<../../../../Experiments/R113_CausalStructureDissection/FILE_GUIDE.md>)）發現：** V42 跟 R61 是同一份模型程式，135 個共有權重張量中 112 個逐位元相同；V42 最主要的新行為來自最後的原圖錨定（拿掉後輸出中位改動約 39 灰階）；它的弱 PSF 分支學到的強度係數是 0，拿掉後輸出完全不變。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 舊版論文的 V42 結果、圖表與重現腳本 | [`01_CURRENT_THESIS_RESULTS_V42_CENTER9/`](<../../../Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/README.md>)、[`04_V42_NEURAL_NETWORK_RESULTS/`](<../../../Final_Data_Figures/04_V42_NEURAL_NETWORK_RESULTS/README.md>)，已在 GitHub |
| V42 原表、兩份固定模型與重做（約 51 MB） | Release [`research-v42-history-replay-20261021`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-v42-history-replay-20261021)；`python Tools/replay_lab_v42_history.py --root . --output <新資料夾>`，加 `--native` 跑四次 CPU 推論，細節見 [V42 完整歷史](<../../../../docs/reproducibility/lab_comparisons/V42_HISTORY.md>) |
| 完整模型包（程式、PSF、必要權重，約 403 MB） | [V42 完整包](<../../../../Deliverables/Standalone_Models/V42_SoftLabelSNR_FullStandalone_20260709/README_TW.md>) 的程式在 GitHub；權重在 Release [`research-results-models-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016) |
| 短測程式與測試 | 本資料夾 [scripts/](<scripts>)、[tests/](<tests>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的限制：** 完整包裡的 11,254 組訓練資料與 120 輪全部權重（約 18 GB）只在原電腦上，依保存原則不整包上傳；從 GitHub 取回的重做包沒有重跑 120 輪訓練，只核對了原表、固定模型與 CPU 推論。

## 原始報告

| 文件 | 內容 |
|---|---|
| [V42 短測結果](<V42_SOFTLABEL_SNR_SMOKE_RESULT.md>) | 2026-07-09 的兩輪短測：資料、模型改動、短測指標與測試 |
| [V42 完整歷史](<../../../../docs/reproducibility/lab_comparisons/V42_HISTORY.md>) | 2026-10 整理：短測與完整訓練的分界、實際起點、各個模型檔的身分、欄位錯置的原因 |
| [V42 完整包說明](<../../../../Deliverables/Standalone_Models/V42_SoftLabelSNR_FullStandalone_20260709/README_TW.md>) | 建立時寫的包說明（當時長訓練尚未完成，原文保留） |
| [舊版論文的 V42 結果](<../../../Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/README.md>) | 中心九顆的 CD 與位移結果 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../../../docs/reproducibility/experiments/lab__V42_SoftLabelSNR.md>)與 [Lab 逐輪必要來源核對](<../../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>)。
