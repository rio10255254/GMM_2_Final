# organized_20260310 完整歷史與恢復方式

封存日期：2026-08-01

- 完整快照：`H:\GMM_2_Final_Archive\legacy\organized_20260310\20260801_full_history\snapshot`
- 內容清單：`H:\GMM_2_Final_Archive\manifests\organized_20260310_20260801_full.csv`
- 複製紀錄：`H:\GMM_2_Final_Archive\operation_logs\organized_20260310_20260801_robocopy.log`
- 規模：928 個檔案、2.190 GiB
- 核對：PASS，零缺漏、零不一致

D 槽 `selected_evidence/` 保留 38 份小型核心證據，包含原始 GMF 分數、分析數字、比較摘要與重建清單；完整重建影像與其餘執行輸出都在 H 槽快照內。

執行結果：`external_validation/` 已於 2026-08-01 移除，實際回收 2.191 GiB；刪除後 H 槽 928 個檔案再次核對 PASS。

完整恢復：

```powershell
robocopy H:\GMM_2_Final_Archive\legacy\organized_20260310\20260801_full_history\snapshot Experiments/Legacy/organized_20260310 /E /COPY:DAT /DCOPY:DAT
```

恢復後使用中央清單逐檔核對，回報 PASS 才算完整恢復。
