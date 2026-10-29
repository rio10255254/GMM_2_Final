# 論文改寫交接：R128修正取樣位置後的實驗

整理日期：2026-09-20。本包只把已核對的成果集中供論文改寫，未重新訓練、未改論文Word、未搬動或覆寫原始資料。

## 先讀順序

1. [論文改寫交接與結論界線](HANDOFF_FOR_THESIS.md)
2. [Raw與R128完整比較、10張圖及逐顆資料](01_Raw_R128_Comparison/README.md)
3. [R128單獨的詳細結果與4張图](02_R128_Detailed_Results/README.md)
4. [新舊取樣位置示意](03_Sampling_and_SEM/selected_nine.png)

推薦論文主圖：[Raw/R128平均曲線＋±1標準差疊圖](01_Raw_R128_Comparison/figures/09_mean_error_sd_overlay.png)，同名SVG可放大排版。[九顆起點輪廓](01_Raw_R128_Comparison/figures/03_contours_position00.png)與[終點輪廓](01_Raw_R128_Comparison/figures/03_contours_position30.png)保留30次觀測與相同尺度。

## 資料夾內容

- 01_Raw_R128_Comparison：主報告、位移／尺寸／輪廓／SEM對照、10張PNG與一張SVG、所有統計明細。
- 02_R128_Detailed_Results：R128專頁、逐顆／逐位置／逐方向數據、4張細節圖。
- 03_Sampling_and_SEM：修正後九顆的位置、SEM編號與方向證據；歷史SEM排序已確定，九月相對方向仍是工作推定。
- 04_Source_and_Verification：Raw/R128原邊界點、圓心、追蹤、徑向輪廓、固定模型設定、來源路徑及已完成核對。
- 05_Script_Reference：實際分析程式副本及使用範圍說明。
- SOURCE_COPIES.json與MANIFEST.json：原檔來源、逐檔雜湊；verify_package.py可用標準Python核對。

未加入全部原圖、重建影像或模型權重；其原始位置保留在來源記錄。JSON與程式中的絕對路徑屬原專案來源，報告、CSV及本資料夾内圖片可獨立閱讀。資料夹内旧package_manifest.json描述原成果子包；本交接包以根目錄MANIFEST.json為完整清單。
