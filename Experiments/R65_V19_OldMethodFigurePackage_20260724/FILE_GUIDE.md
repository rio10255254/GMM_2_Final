# R65：論文第 19 版的圖表包（舊的位移量法）

[研究時間線](<../../docs/research/TIMELINE.md>) · [同一天用新量法重算的 R64](<../R64_IsocontourDisplacementReanalysis_20260724/FILE_GUIDE.md>) · [下一版論文的 R66](<../R66_V20_TraceabilityFigures_20260725/FILE_GUIDE.md>)

**一句話：** 名稱裡的「V19」是**論文稿的第 19 版**（「論文完整版_20260716_v19_第六章更新版」），不是模型。2026-07-24 為這一版的第六章整理了 35 張新圖（位移改善、消融、多模型比較），位移一律沿用原本的**最大梯度邊界**量法，並寫了從第 18 版自動產生第 19 版 Word 檔的程式。這是當時論文的圖表版本，不是現在論文的主結果。

| | |
|---|---|
| 結果 | **分析**（歷史圖表版本，不冒充目前論文主結果） |
| 時間 | 2026-07-24 |
| 實驗條件 | C：實驗室顯微系統；同 V42 論文結果與 R63、EDSR／NAFNet 對照的資料 |
| 產出 | 35 張新圖（各有 PNG、PDF、MATLAB FIG）、20 張保留素材、第 19 版論文 Word 檔 |

## 這輪在做什麼

把第六章可能新增或取代的圖表集中整理：位移改善、消融、多模型比較三組分開呈現，只畫實際選取的 30 步，固定顏色、字型、圖例位置，圖內不放標題與說明文字（說明全部放圖說）。

## 結果

**位移改善（最大梯度量法，柱的平均絕對誤差，nm）：**

| 序列 | 原圖 | Wiener | V42 |
|---|---:|---:|---:|
| 50×、0.5 µm | 5.252 | 4.067 | 3.065 |
| 50×、1.0 µm | 6.981 | 3.887 | 3.355 |
| 20×、0.5 µm | 13.126 | 12.781 | 11.735 |
| 20×、1.0 µm | 12.819 | 9.125 | 8.814 |

用舊量法，V42 在四組都最低；同樣的資料用 R64 的新量法，V42 只在兩組最低（見 [R64](<../R64_IsocontourDisplacementReanalysis_20260724/FILE_GUIDE.md>)）。多模型比較裡，EDSR-x1 在 50×、20× 柱的平均誤差都比 V42 低。

## 讀這些數字要知道的事

1. **同一天有兩套圖。** R65 是舊量法、R64 是新量法；兩套都保留，因為量法的選擇本身就影響結論。
2. **EDSR-x1 的 20×、0.5 µm 柱有 2 步沒通過九顆柱有效性檢查**，逐步圖用斷線表示，摘要值用其餘 28 步。
3. **論文 Word 檔不在 GitHub 上**，依論文與專案的分工放在個人雲端；這裡保留的是產生它的程式。現在的論文以 R152／R153 為主結果。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 產圖、統一 CD 重算、論文組版與檢查程式 | 本資料夾根目錄（`plot_v19_old_method_figures.m`、`reanalyze_multimodel_cd_unified.py`、`build_thesis_v19.py`、`qa_*.py` 等），已在 GitHub |
| 圖、圖說索引、資料核對 | [論文證據區 07_V19_OLD_METHOD_FIGURE_PACKAGE_20260724/](<../../Thesis_MOSR_Evidence/Final_Data_Figures/07_V19_OLD_METHOD_FIGURE_PACKAGE_20260724/README.md>)、[圖說索引](<../../Thesis_MOSR_Evidence/Final_Data_Figures/07_V19_OLD_METHOD_FIGURE_PACKAGE_20260724/V19_FIGURE_INDEX_zh-TW.md>)、[資料核對](<../../Thesis_MOSR_Evidence/Final_Data_Figures/07_V19_OLD_METHOD_FIGURE_PACKAGE_20260724/99_qa/DATA_VALIDATION_SUMMARY.md>) |

`lo_profile_v19/` 是轉檔時 LibreOffice 留下的設定資料夾，不是研究內容。

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

## 原始報告

| 文件 | 內容 |
|---|---|
| [圖表包 README](<../../Thesis_MOSR_Evidence/Final_Data_Figures/07_V19_OLD_METHOD_FIGURE_PACKAGE_20260724/README.md>) | 使用原則、資料夾內容、輸出格式、範圍 |
| [資料核對](<../../Thesis_MOSR_Evidence/Final_Data_Figures/07_V19_OLD_METHOD_FIGURE_PACKAGE_20260724/99_qa/DATA_VALIDATION_SUMMARY.md>) | 完整性與三組實驗的數字 |
| [README](<README.md>)、[MANIFEST](<MANIFEST.md>) | 2026-10-16 補建的入口 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R65_V19_OldMethodFigurePackage_20260724.md>)。
