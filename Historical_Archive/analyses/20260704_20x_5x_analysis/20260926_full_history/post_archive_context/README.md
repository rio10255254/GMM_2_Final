# 20x / 5x 實拍分析資料入口

這裡保存四組實拍原圖、模型重建、候選比較及外部量測資料。

## 原始與引用資料

- raw_inputs：四組原始照片，共 200 張。保留 D 槽原位置，後續多輪分析直接讀取這些來源。
- 四個 r61_v16_psfoff 資料夾：目前被後續分析引用的 R61 輸出，保留原位置。
- external_gmf_packages、_gmf_scores：外部量測交付、回傳結果與未回傳狀態，須保留證據脈絡。
- input_mapping.csv、input_summary.csv、prepare_inputs.py：原圖對應與輸入準備方法。
- 各候選的 manifest、日誌及分析摘要：用來追查模型與影像來源。

## 正在安排的歷史封存

2026-09-26 重新盤點：全區約 91.517 GiB；其中 reconstructions 約 30.772 GiB，238 個 R62 候選資料夾約 34.876 GiB，64 個融合候選資料夾約 9.380 GiB。這些是原檔案標示容量，尚不是已回收容量。

逐批核對報告引用、完整 H 副本與 D 保留內容後，才列出可移除的歷史輸出。這份入口不授權整個資料夾刪除；目前本區尚未完成新的 H 快照或移除原件。

整體規劃見 [三區移植規劃](../docs/operations/PROJECT_STORAGE_MIGRATION_PLAN_20260926.md)，執行進度見 [實際執行紀錄](../docs/operations/PROJECT_STORAGE_MIGRATION_EXECUTION_20260926.md)。詳細盤點保存於 H:/GMM_2_Final_Archive/operation_logs/Storage_Migration_20260926/analysis_20260704_stage2_preflight.json。


## 2026-09-26 完整封存狀態

已完成 32,262 檔、約 91.517 GiB 的完整 H 副本，來源與副本逐檔 SHA-256 一致，複製期間來源未變；D 原件仍在，這批尚未回收 D 空間。引用核對顯示 442 個大型候選資料夾中 440 個名稱見於其他專案文字檔，另兩個沒有精確名稱引用但仍待證實。

請由 ARCHIVE_POINTER_20260926.md 查找完整 H 副本與恢復方式。下方先前「尚未完成 H 快照」文字是封存前的歷史描述。
