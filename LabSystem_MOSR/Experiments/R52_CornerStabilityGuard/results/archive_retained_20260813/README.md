# R52 D 槽精簡保留包

這個資料夾保留 R52 負結果仍值得在 D 槽快速查閱的證據。大型完整歷史位於 H 槽；恢復入口是實驗根目錄的 `ARCHIVE_POINTER_R52_20260813.md`。

## 內容

- `data_manifests/`：正式訓練與驗證資料的原始 manifest。
- `formal_run_evidence/`：100 輪正式訓練的日誌、曲線、代表影像，以及 `latest`、`best_tradeoff`、`best_detail_guarded` 三個代表模型。
- `smoke_run_evidence/`：smoke 訓練的精簡日誌、曲線與代表影像。
- `corner_validation/`：真實角點驗證的完整表格、JSON 與代表圖。

38 個來源檔案共 196,263,227 bytes，建立時已逐檔比對 SHA-256，全部一致。這個保留包不代表 R52 通過或升級；R52 仍是角點守門失敗的負結果。
