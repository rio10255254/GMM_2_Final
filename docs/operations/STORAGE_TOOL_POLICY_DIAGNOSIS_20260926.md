# 刪除遭阻擋的深入診斷

日期：2026-09-26

## 結論

已定位到 Codex 的命令執行前政策檢查。三次真實拒絕都發生在建立命令程序前，沒有交給 PowerShell 或 Windows 檔案系統執行。因此檔案鎖定、目錄讀取權限、PowerShell 執行原則及專案容量守門程式均不是這則 blocked by policy 訊息的直接來源。

最可能是實際桌面運行版本內建的命令安全／強制刪除保護。尚不能從現有紀錄證明命中的具體分支，或保證改成可人工核准後即可刪除。

先前將其寫成「自動審查拒絕」不夠精確。實際 reviewer 為 user、approval_policy 為 never，沒有自動審查決定或拒絕理由。正確稱呼為「Codex 執行前政策拒絕」。

## 診斷完成標準與結果

- 找到真正工具拒絕，而不是助理摘要中引用錯誤：通過，共三次。
- 確认命令是否啟動：未啟動，CreateProcess Rejected、0 秒、沒有該刪除的 CommandExecution 程序事件。
- 用實際運行版本重核本機規則：通過，仍沒有匹配規則。
- 查明實際有效核准及審查設定：通過，由工作階段及桌面啟動紀錄交叉核對。
- 核對目標根目錄的 Windows 屬性及權限：通過，沒有根目錄唯讀、外部連結或明確拒絕項目。
- 確认是否可精確證明程式內部分支：現有日誌不足，未證明。
- 不重試刪除、不改安全設定、不操作其他活動工作：遵守。

## 三次原始拒絕

| 本地時間 | 動作 | 原始工作階段紀錄行 | 結果 |
|---|---|---:|---|
| 2026-09-25 01:55:10 | 七輪歷史資料批次清理 | 1153 | 啟動程序前拒絕 |
| 2026-09-25 01:55:35 | 單一 R89 資料目錄清理 | 1161 | 啟動程序前拒絕 |
| 2026-09-26 11:05:33 | 單一 R53 資料目錄清理 | 2383 | 啟動程序前拒絕 |

三次皆為 danger-full-access、approval_policy=never。錯誤包含 CreateProcess / Rejected / rejected: blocked by policy，沒有 Windows 的 Access denied、分享衝突、路徑過長或 PowerShell 解析錯誤。

已保存原始命令、拒絕內容、時間與工作階段設定到 exact_policy_rejections.json，沒有重新執行命令。

## 實際版本與先前檢查的差異

桌面實際 app-server 為 0.158.0-alpha.2，路徑：
C:/Users/Rio/AppData/Local/OpenAI/Codex/bin/d23520d1e41bfb24/codex.exe。

先前使用的另一份 CLI 為 0.136.0。先前檢查只代表該 CLI 對本機規則檔的結果，不能涵蓋桌面版本內建的安全判斷。

本次已使用實際 0.158.0-alpha.2 的唯讀 execpolicy check，核對完整原 R53 命令及實際 PowerShell 路徑。結果仍為 matchedRules: []。規則檔共 74 個 allow，沒有 prompt 或 forbidden。已查看使用者層、D 槽祖先及專案層、常見 ProgramData 位置，未找到其他本機規則或 requirements/managed_config 檔案；這不排除非檔案形式的受管限制。

實際執行檔的命令政策訊息區同時含有：
「rm -f style commands are not permitted. Use a safer approach」及
「rejected: blocked by policy」。

這是程式內存在強制刪除保護的直接證據；它與本次命令對應關係仍是推斷，不能僅靠字串位置認定已證明具體分支。二進位讀取及規則檢查沒有執行受拒絕命令。

## 有效設定從哪裡來

桌面日誌顯示介面推導值為 on-request / workspaceWrite，但送出時沒有明確指定權限，採 app-server 預設。伺服器實際回覆：

- responseApprovalPolicy / resolvedApprovalPolicy：never
- responseApprovalsReviewer：user
- responseActivePermissionProfile：:danger-full-access
- responseSandboxPolicy：dangerFullAccess
- useAppServerPermissionDefault：true

使用者 config.toml 與原始 turn_context 同樣為 never / danger-full-access。沒有證據顯示「已開啟完整存取」能取消程式所有內建命令限制；never 則確實讓此工作階段沒有人工核准請求。這也解釋為何沒有出現可供點選的核准卡片。

本次 task 的已保存事件中沒有 approval/reviewer 決定；官方說明亦指出 never 不會形成一般自動審查請求。

## Windows 與專案層

- R53 目標根目錄普通、非唯讀、非外部連結。
- 根目錄 ACL 有 Authenticated Users 的 Modify/Synchronize 允許；管理員 FullControl，未發現根目錄明確 Deny。
- PowerShell LocalMachine 為 RemoteSigned；其他執行原則層為 Undefined。本次內嵌命令未啟動，此原則不產生觀察到的拒絕。
- 專案容量守門工具沒有出現在被拒絕命令裡。即使其狀態仍有保護標記，它也沒有執行到這次命令內。
- 未完整稽核四萬個檔案的權限或占用情況；這些可在正式放行後另做移除前檢查，但不是本次啟動前拒絕的來源。

## 正式處理方向

1. 先讓桌面工作的有效設定與期望的人工核准模式一致，由使用者或介面正式設定，而不是只看介面推導值或修改規則免除被拒絕動作。
2. 若該模式能提出對單一已核對清理目錄的正式請求，需取得清楚的拒絕理由或正式放行結果，才能確認具體內建限制。
3. 若同樣在執行前直接拒絕，將本紀錄的實際版本、精確命令、時間、設定及錯誤提供官方支援。當前執行工具沒有暴露內建判斷的細項。
4. 不保證改成 on-request 可解除內建禁止。此診斷未修改 config、規則、審查設定或有效權限，未測試替代刪除方式。

此處也不再將 /approve 當作已確認適用的解法：官方僅描述終端介面的自動審查拒絕重試，本次沒有自動審查決定。

## 證據位置

H:/GMM_2_Final_Archive/operation_logs/Storage_Migration_20260926/

- exact_policy_rejections.json：三次真正啟動前拒絕。
- deep_policy_runtime_evidence.json：實際程序、版本、啟動時間。
- actual_runtime_binary_policy_strings.json：程式內政策訊息。
- desktop_effective_permission_fields.json：介面推導與伺服器有效設定。
- desktop_policy_log_headings.json：相關日誌位置。
- deep_policy_diagnosis_final.json：本次結論與限制。

研究資料未刪除，目前訓練未停止。R53/R56 封存狀態與清理清單保持原記錄。

## 官方參考

- [命令規則與唯讀規則檢查](https://learn.chatgpt.com/docs/agent-configuration/rules)
- [核准、權限與工作階段設定](https://learn.chatgpt.com/docs/agent-approvals-security)
- [自動審查適用條件與拒絕流程](https://learn.chatgpt.com/docs/sandboxing/auto-review)


## 使用者要求解決後的設定修正

已完成本專案人工核准入口修正，磁碟設定載入通過；當前已啟動這一輪仍沿用舊權限，研究資料尚未刪除。詳見 [修正及實際驗證](STORAGE_APPROVAL_ROUTING_FIX_20260926.md)。上述深入診斷描述的是修正前的設定與拒絕紀錄。


## 最終實際解決結果

新一輪已切換可人工核准模式；正式 require_escalated 請求獲使用者核准後，與先前相同的 R53 原生移除命令成功。剩餘 18 個目錄亦按正式核准移除。這證明先前拒絕不是任何情況下都不可刪除的絕對禁止；可以透過正式核准途徑完成。沒有停用保護或新增寬泛刪除免審規則。此前對具體內部分支的推斷仍不作程式內部已證明的主張。

R53/R56 本批封存與精簡完成。完整移除後核對記錄見 storage_execution_20260926/post_cleanup_verification.json。
