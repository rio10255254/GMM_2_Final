# 歷史重建副本清理與恢復（2026-10-21）

52 個已核對的歷史重建目錄、10,500 份影像只移除了 D 槽重複副本，原位置仍可直接讀取獨立 H 工作副本。此次實際多出 33,073,446,912 bytes（約 33.07 GB），沒有把較早 R87 的清理重算。

200 張原始拍攝、外部量測包、正式原表、四組 R61 論文結果及這 52 目錄以外的 21,763 份現存檔案保留，原數表及文件核對未改。其他 R62、融合及舊候選不在本次移除範圍。

- 完整封存：`H:\GMM_2_Final_Archive\analyses\20260704_20x_5x_analysis\20260926_full_history\payload`。
- 獨立工作副本：`H:\GMM_2_Final_Archive\compatibility_views\20260704_20x_5x_analysis\20260926\reconstructions`。
- 每個原位置及兩份 H 來源：本目錄 `ARCHIVE_SCOPE_20261021.json`。
- 本次完整核對與實際刪除紀錄：`H:\GMM_2_Final_Archive\reproducibility\20261021_d_cleanup`。

刪除前，各目錄三份檔案的完整內容逐一相同；切換後已核對全部原入口、檔案集合、大小與原修改時間，並實際讀取首／中／尾批次的代表影像。完整封存與工作副本分開，後續若產生新的結果，請另開新的輸出目錄，避免改寫已固定歷史。

如需再建立 D 槽實體副本，先選一個新的空目錄，再從完整封存複製；不要覆寫目前入口。以下以本次第一個歷史批次為例：

```powershell
robocopy "H:\GMM_2_Final_Archive\analyses\20260704_20x_5x_analysis\20260926_full_history\payload\reconstructions\reconstruct_progress_best_tradeoff_in_bmp_20260623_200020" "D:\GMM_2_Final_Restore\reconstruct_progress_best_tradeoff_in_bmp_20260623_200020" /E /COPY:DAT /DCOPY:DAT /XJ /R:1 /W:1
```

完成複製後，使用本輪紀錄中的對應檔案清單核對內容。原位置目前已可讀，正常閱讀或重新分析不需要先複製一整套。
