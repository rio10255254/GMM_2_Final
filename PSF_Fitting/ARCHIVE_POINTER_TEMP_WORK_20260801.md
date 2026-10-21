# 2026-08-01 舊文件工作區隔離說明

這次只處理 PSF 資料夾中三個由文件編輯與渲染工作產生的舊工作區：`.codex_tmp`、`.codex_work`、`.codex_docx_work`。正式 PSF 程式、quick recalibration、輸入資料、輸出結果、論文文件與測試均不在清理範圍。

- H 槽隔離快照：`H:\GMM_2_Final_Archive\quarantine\PSF_Fitting_editor_scratch\20260801\snapshot`
- 實體內容：6,854 個檔案，1,899,798,538 bytes（1.769 GiB）
- 核對：三份清單全部 PASS
- 隔離到期日：2026-08-31
- 清單：`H:\GMM_2_Final_Archive\manifests\PSF_Fitting_codex_*_20260801.csv`

執行結果：三個 D 槽舊工作區已於 2026-08-01 移除，實際回收 1.782 GiB；移除後再次核對 H 槽三份清單全部 PASS。這些內容不在資源回收筒，可在隔離期限內依下方方式恢復。

完整恢復：

```powershell
robocopy H:\GMM_2_Final_Archive\quarantine\PSF_Fitting_editor_scratch\20260801\snapshot D:\GMM_2_Final\PSF_Fitting /E /COPY:DAT /DCOPY:DAT
```

資料夾中的套件連結不是實體內容，未重複複製；若需要重啟舊工作區，依原專案設定重新安裝套件即可。
