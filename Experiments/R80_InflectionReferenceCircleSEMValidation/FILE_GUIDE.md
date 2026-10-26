# R80（取邊量法）：不用灰階門檻，改用轉折點與參考圓量 CD

[研究時間線](<../../docs/research/TIMELINE.md>) · [同號的另一個 R80（R79 早晚權重）](<../R80_R79E23vsE100GeneralizationValidation/FILE_GUIDE.md>) · [沿用這套量法的 R81](<../R81_MultiArchitectureReferenceCircleBenchmark/FILE_GUIDE.md>) · [ACM 輪廓的 R69](<../R69_ACMContourSEMValidation/FILE_GUIDE.md>)

**一句話：** 2026-08-05 前後建立一套完全不用灰階門檻的量法：先用 ACM 取每顆柱的粗輪廓，再沿法線找正確極性的最大梯度轉折點，最後擬合最小平方圓（LSC）得到直徑與圓心，另算最小區域圓度（MZC）與內外接圓包絡。用這套量法重看 V42：36 顆柱的 SEM 輪廓與位移都比原圖好；但 **50× 靜態九顆柱的 CD，V42（100.9 nm）比原圖（51.9 nm）差，Wiener（22.0 nm）最好**。

| | |
|---|---|
| 結果 | **分析**（量法研究；需保留與完整輪廓讀法、門檻讀法的差別） |
| 時間 | 2026-08-05 前後 |
| 實驗條件 | 6/18 的 50×、20× 靜態影像（中心九顆柱）；R69 的 36 顆柱 × 12 張曝光 SEM；7 月的四組位移序列 |
| 比較對象 | 原圖、Wiener（NSR 0.0565，兩倍率共用）、V42 第 120 輪（文件裡稱 MOSR） |

## 結果

**靜態九顆柱（LSC 直徑對 SEM 的絕對誤差中位數，nm）：**

| 倍率 | 原圖 | Wiener | V42 |
|---|---:|---:|---:|
| 20× | 150.1 | **56.9** | 268.3 |
| 50× | 51.9 | **22.0** | 100.9 |

V42 的 MZC 圓度在兩個倍率都比原圖好（50×：114.3 對 217.1 nm），但 20× 的四重對稱分量明顯偏高（3.7%）。

**36 顆柱 SEM 輪廓（跨 12 張曝光的逐顆中位數）：**

| 指標 | 原圖 | V42 | 配對檢定 |
|---|---:|---:|---|
| LSC 直徑誤差 | 91.8 nm | **84.5 nm** | p = 2.9e-11 |
| 相對 SEM 輪廓的徑向誤差 | 48.4 nm | **42.8 nm** | p = 2.9e-11 |
| 輪廓相關係數 | 0.557 | **0.877** | p = 5.8e-11 |
| MZC 圓度誤差 | 110.6 nm | **26.5 nm** | p = 1.6e-9 |

**位移（LSC 圓心差，四序列平均）：** 步階標準差 原圖 8.88、Wiener 7.91、V42 **7.29** nm；九顆柱離散度 原圖 12.55、Wiener 5.98、V42 **4.89** nm。

## 讀這些數字要知道的事

1. **SEM 那組影像的比例尺不一樣。** 它是依 5 µm 週期重新取樣的 SEM 配對堆疊，比例是 5 µm 除以實測週期，不能套用原生 50× 的 0.069 µm/px。
2. **換量法，CD 的結論會反過來。** 之前用門檻區間量（R63、EDSR／NAFNet 對照），V42 的 50× CD 跟原圖差不多或更好；用轉折點與 LSC 量，V42 明顯比原圖差。兩種結果都是原始紀錄。
3. **Wiener 在這套量法下的 CD 最好**，這在之後 R81 的 13 模型比較裡仍成立。
4. 位移的影格名單由原圖在分析前鎖定，Wiener 與 V42 不參與挑選。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 量法核心、靜態九顆、SEM 36 顆、位移程式 | 本資料夾 [scripts/](<scripts>)，已在 GitHub；核心是 [reference_circle_core.py](<scripts/reference_circle_core.py>) |
| 8 張圖（流程、疊圖、CD 誤差、圓度、曝光、視野位置、位移） | [results/figures/](<results/figures>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的限制：** 逐顆量測表不在 git 裡。

## 原始報告

| 文件 | 內容 |
|---|---|
| [靜態九顆](<results/STATIC_CENTER9_READOUT_TW.md>) | 兩倍率三方法的 LSC、MZC、四重對稱 |
| [SEM 36 顆](<results/SEM36_READOUT_TW.md>) | 輪廓驗證與配對檢定 |
| [LSC 圓心位移](<results/DISPLACEMENT_LSC_READOUT_TW.md>) | 四序列的位移結果 |
| [README](<README.md>) | 2026-10-16 補建的入口 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R80_InflectionReferenceCircleSEMValidation.md>)。
