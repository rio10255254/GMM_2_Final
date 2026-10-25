# R64：換一套位移量法，重算三組實驗

[研究時間線](<../../docs/research/TIMELINE.md>) · [前一輪 R63](<../R63_CausalBoundaryMotionAblation/FILE_GUIDE.md>) · [同一天用舊量法做的 R65](<../R65_V19_OldMethodFigurePackage_20260724/FILE_GUIDE.md>) · [量法比較的出處](<../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/FILE_GUIDE.md>)

**一句話：** 2026-07-24 決定試用新的位移量法：每顆柱取五條水平弦、30%～70% 五個灰階門檻的等強度輪廓交點，取中位數當中心，並改用平台的**實際回授**位置當參考。R64 用這套量法，把三組已有的實驗（Raw／Wiener／MOSR 位移改善、R63 消融、多模型比較）全部重算一次。沒有新訓練。重算後 R63 的消融結論有變：移除原圖位置錨定，九顆柱位移離散度增加 35%；位移安全上採樣從「支持」降為「趨勢」。

| | |
|---|---|
| 結果 | **分析**（既有數據重算，保留原量法與修訂量法的差別） |
| 時間 | 2026-07-24 |
| 實驗條件 | C：實驗室顯微系統；7 月的四組位移序列，Raw 預先鎖定的 30 步，平台實際回授 |
| 重算對象 | Raw、Wiener、V42 的位移改善；R63 的 16 個消融版本；Raw、NAFNet、EDSR-x1、V42 的多模型比較 |

## 這輪在問什麼

舊的「最大梯度邊界」量法容易受振鈴和多重斜率峰影響。換成跟 CD 定義一致的等強度輪廓量法，結論會不會變？

## 結果

**位移改善（只看柱，平均絕對誤差，nm）：**

| 序列 | 原圖 | Wiener | V42 | 最好 |
|---|---:|---:|---:|---|
| 50×、0.5 µm | 2.908 | 2.695 | 2.730 | Wiener |
| 50×、1.0 µm | 3.122 | 2.958 | 2.820 | V42 |
| 20×、0.5 µm | 14.226 | 15.426 | 12.509 | V42 |
| 20×、1.0 µm | 8.040 | 8.535 | 9.208 | 原圖 |

**R63 消融重算（四序列合併）：**

| 移除的設計 | 位移平均誤差變化 | 九顆柱離散度變化 |
|---|---|---|
| 原圖位置錨定 | +0.674 nm（+9.8%，95% 區間 0.17～1.18） | **+2.369 nm（+35.3%）**，50×、20× 都有 |
| 幾何錨定 | — | +0.232 nm（+3.5%） |
| 幾何與位移限制都拿掉 | — | +0.321 nm（+4.8%） |
| 已知位移監督 | +0.084 nm（+1.2%） | — |
| 位移安全上採樣換成一般上採樣 | — | +0.436 nm，兩種子同方向但區間跨零 |

**多模型比較：** V42 在 50× 柱最低（2.775 nm），20× 柱次於 EDSR-x1；孔的最低分別是原圖（50×）和 EDSR-x1（20×）。

## 讀這些數字要知道的事

1. **量法會改變因果結論。** R63 用舊量法時，原圖位置錨定的作用主要在 CD 與振鈴，位移上沒有支持；R64 用新量法時，它對九顆柱一致性的作用最明顯。位移安全上採樣則反過來。兩組結果都保留，引用時要說明用的是哪一套量法。
2. **Wiener 只有處理柱的區域。** 留存的 20× Wiener 影像在孔的區域跟原圖逐像素相同，所以位移改善只比柱。
3. **V42 沒有全面領先。** 20×、1.0 µm 的誤差高於原圖，50× 兩組的九顆柱離散度也高於原圖與 Wiener。
4. 選新量法的理由應該建立在邊界定義與合成驗證上，不是因為它讓哪個模型排名較好（見[量法比較報告](<../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/evaluation/measurement_method_comparison_20260724/METHOD_COMPARISON_REPORT_zh-TW.md>)）。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 重算程式與 MATLAB 畫圖 | 本資料夾 [run_isocontour_reanalysis.py](<run_isocontour_reanalysis.py>)、[plot_isocontour_reanalysis.m](<plot_isocontour_reanalysis.m>)，已在 GitHub |
| 報告、圖表索引與圖 | [論文證據區 06_DISPLACEMENT_EXPERIMENTS_ISOCONTOUR_20260724/](<../../Thesis_MOSR_Evidence/Final_Data_Figures/06_DISPLACEMENT_EXPERIMENTS_ISOCONTOUR_20260724/README.md>) |
| 被重算的原始量測 | [R63](<../R63_CausalBoundaryMotionAblation/FILE_GUIDE.md>)、[EDSR／NAFNet 對照](<../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/FILE_GUIDE.md>)、[V42 論文結果](<../../Thesis_MOSR_Evidence/Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/README.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

## 原始報告

| 文件 | 內容 |
|---|---|
| [新版位移量測實驗報告](<../../Thesis_MOSR_Evidence/Final_Data_Figures/06_DISPLACEMENT_EXPERIMENTS_ISOCONTOUR_20260724/EXPERIMENT_REPORT_zh-TW.md>) | 統一量法、三組實驗的結果與資料完整性 |
| [圖表索引](<../../Thesis_MOSR_Evidence/Final_Data_Figures/06_DISPLACEMENT_EXPERIMENTS_ISOCONTOUR_20260724/FIGURE_INDEX_zh-TW.md>) | 每張圖的圖說 |
| [README](<README.md>)、[MANIFEST](<MANIFEST.md>) | 2026-10-16 補建的入口 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R64_IsocontourDisplacementReanalysis_20260724.md>)。
