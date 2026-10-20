# R97 保存與來源清單

seed 970043；2,433,774 參數。48 輪完成；正式執行在第 1 輪後遇到檔案存取拒絕，從同一輪模型恢復一次，原表 1–48 無重複。後訓練協定固定第 48 輪平均權重，較早模型只作歷程分析。

| 類別 | 實際保存 |
|---|---|
| 原設計與方法 | config、model、training、inference、scripts、tests；原始碼不因整理改變 |
| 原輸入 | 本輪四張固定預覽；R93 共用合成庫另有完整 GitHub 附件 |
| 生成紀錄 | 512 個原位置、2163916440 bytes |
| 模型檔 | 28；包含原測試／別名，不能算成獨立訓練數 |
| 影像 | 396，含全部現存比較與重建 |
| 完整固定清單 | docs/reproducibility/four_rounds/R97_RECORD_MANIFEST.json.gz |
| 正式審查 | reports/R97_AUDIT.md |
| GitHub 固定版本 | r97-complete-record-20261021 |

原 MANIFEST 在 `docs/history/R97_MANIFEST_BEFORE_PROVENANCE_AUDIT_20261021.md` 原封保留。保存不授權刪除，也不更改科學判決。
