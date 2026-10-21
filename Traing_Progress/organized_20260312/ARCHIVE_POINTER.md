# organized_20260312 完整歷史與恢復方式

封存日期：2026-08-01

- 完整快照：`H:\GMM_2_Final_Archive\legacy\organized_20260312\20260801_full_history\snapshot`
- 內容清單：`H:\GMM_2_Final_Archive\manifests\organized_20260312_20260801_full.csv`
- 複製紀錄：`H:\GMM_2_Final_Archive\operation_logs\organized_20260312_20260801_robocopy.log`
- 規模：1,152 個檔案、3.829 GiB
- 核對：PASS，零缺漏、零不一致

D 槽保留 13 份歷史報告與種子、少量 pending 紀錄，以及 1 份 `centerlock_pure` 代表模型。大型長跑、舊狀態、smoke log 與外部重建都可從 H 槽恢復。

執行結果：`archive/` 與 `external_validation/` 已於 2026-08-01 移除，實際回收 3.831 GiB；刪除後 H 槽 1,152 個檔案再次核對 PASS。

完整恢復：

```powershell
robocopy H:\GMM_2_Final_Archive\legacy\organized_20260312\20260801_full_history\snapshot D:\GMM_2_Final\Traing_Progress\organized_20260312 /E /COPY:DAT /DCOPY:DAT
```

恢復後使用中央清單逐檔核對，回報 PASS 才算完整恢復。
