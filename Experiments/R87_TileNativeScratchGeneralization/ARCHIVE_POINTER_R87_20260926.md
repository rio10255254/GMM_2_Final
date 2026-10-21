# R87 完整歷史封存入口

2026-09-26 已建立 R87 完整 H 副本：5,588 檔、11.7650 GiB，來源與副本逐檔 SHA-256 一致，複製期間來源未變。D 槽原件（包括合成資料、完整正式 run、權重、失敗與驗證證據）全部保留；本批實際回收 0 bytes。中央登錄仍標示保護，後續須另核對下游資料相依及可重建配方才精簡。

完整副本：H:\GMM_2_Final_Archive\experiments\R87_TileNativeScratchGeneralization\20260926_full_history

來源及 SHA-256 清單：H:\GMM_2_Final_Archive\experiments\R87_TileNativeScratchGeneralization\20260926_full_history\source_manifest.csv

恢復時由 H 的 payload 按 R87 實驗根目錄的相對路徑複製回原位置，再按 source_manifest.csv 核對。這份副本不改變 R87 未升級的研究結論。

## 2026-10-20：D 槽合成陣列副本精簡完成

依使用者要求保留目前完整存取、不跳人工核准的模式，先重新逐檔核對 D 副本、H 完整封存及獨立 H 工作副本，5,152 檔全部符合原凍結內容；再只嘗試一次原生刪除。這次執行成功，移除的 D 實體檔案共 12,155,752,448 bytes；同期間量到 D 可用空間增加 12,176,003,072 bytes（11.3398 GiB），兩種數字分別記錄。

兩個 `data/r87_formal_scene_pairs/arrays`、`data/r87_smoke_scene_pairs/arrays` 原位置現指向 `H:/GMM_2_Final_Archive/compatibility_views/R87_TileNativeScratchGeneralization/20261016/data/` 的各自獨立工作副本，不再占用一套 D 實體影像。不可變完整封存未修改。工作副本缺少的 smoke manifest 已由完整封存補齊，與 D 保留清單及封存原件的內容完全相同。

刪除後核對原保留 438 檔內容未變，之後只更新本封存入口說明。原生讀取程式的正式資料首／中／尾三組及 smoke 首／中／尾三組，透過原 D 位置與 H 工作位置得到完全相同的輸入、答案、位置與角色。沒有啟動新訓練；H 槽正在進行的 R152 v8、R152/R153 論文內容、原始照片、R87 模型及科學報告均保留。20x/5x 與其他批次未清理。

本次精確指令、刪除前後核對、空間差異與活動程序紀錄：`H:/GMM_2_Final_Archive/operation_logs/R87_Cleanup_Trial_20261020/`；完成收據為 `post_cleanup_verified.json`。

原 D 的兩個 arrays 入口現在是 H 工作資料的查找入口，不應再被視為 D 上的另一套重複影像。若未來需要重新放回 D，先恢復到新的空目錄並核對，再另外處理入口；不要直接覆寫既有入口而改到 H 工作內容。
