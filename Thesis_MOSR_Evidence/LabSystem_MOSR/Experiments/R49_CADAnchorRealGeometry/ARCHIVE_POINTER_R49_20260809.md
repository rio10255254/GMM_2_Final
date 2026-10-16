# R49 完整歷史封存入口

R49 已完成 100 輪正式訓練，但真實 checkboard 角點驗證失敗，屬不可升級的負結果。2026-08-09 的兩套資料、三次訓練、三組重建、三組 GMF 準備影像與角點驗證完整保存於：

`H:\GMM_2_Final_Archive\lab_system\R49_CADAnchorRealGeometry\20260809_full_history\snapshot`

精確來源、檔案數、相依資料與 D 槽保留邊界見 `ARCHIVE_SCOPE_R49_20260809.json`。D 槽保留正式報告、資料 manifest、產生與訓練程式、測試、訓練紀錄與曲線、角點證據及恢復入口；完整影像、逐輪模型與重複重建需從 H 槽依清單恢復。

R53 的資料產生程式會引用 R49 CAD-anchor source。需要重做 R53 時，先依本入口恢復 `Training_Data/r49_cad_anchor_source`，不要改用 R55 內的歷史副本冒充原始來源。

恢復前先讀 H 槽批次內的 `ARCHIVE_RECORD.md`，並使用 `H:\GMM_2_Final_Archive\manifests\Lab_R49_*_20260809.csv` 逐項核對。
