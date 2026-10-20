# 人工核准入口設定修正

日期：2026-09-26

## 2026-10-20：依使用者要求撤回專案核准覆寫

使用者要求維持原有模式，不使用專案額外指定的人工核准。已先在 H 槽保存原設定，再移除本專案 `.codex/config.toml`；該檔僅有兩項核准設定及說明，沒有其他專案選項。個人設定檔未修改，專案回歸沿用個人設定。原設定與本次核對紀錄在 `H:/GMM_2_Final_Archive/operation_logs/Codex_Project_Defaults_20261020/`。

本次已啟動對話仍為 `never / danger-full-access`。撤回專案覆寫不等於解除內建執行限制，亦未重試研究資料刪除。最早的刪除拒絕發生於 2026-09-25，早於這份 2026-09-26 新增的核准設定；不能將原始阻擋歸因於它。下文保留當時透過人工核准完成 R53/R56 清理的歷史經過，不代表目前仍採用該專案設定，也不是日後重新加入該設定的授權。

移除後已用目前桌面正在使用的同一份程式，僅讀取本專案的設定，確認為 `never / user / danger-full-access`；原設定備份內容相同，個人設定檔未變。沒有建立新的代理對話或執行刪除，詳細結果見上述紀錄區的 `after_verified.json`。

同日後續使用者明確要求以原模式實際試刪一次 R87 已備份副本。三份 5,152 檔完整重核後，單次原生刪除成功，沒有切換人工核准。刪除後原路徑讀取、保留資料與活動訓練均核對通過，詳見 [R87 最新封存入口](../../Experiments/R87_TileNativeScratchGeneralization/ARCHIVE_POINTER_R87_20260926.md)。以上「沒有執行刪除」描述的是撤回設定當下，後續狀態以本段及 R87 完成收據為準；本次成功沒有證明先前拒絕的內部原因。

## 已實際修正

使用者要求解決刪除命令被政策拒絕的問題。已在本研究專案的 .codex/config.toml 設定需要時提出核准，並由使用者決定：

- approval_policy = on-request
- approvals_reviewer = user

只新增上述兩個專案設定。沒有新增刪除允許規則、關閉內建保護、修改全域設定或擴大檔案存取範圍。

## 已核對

1. 修改前，實際桌面運行版本的 config/read 讀到 never。
2. 修改後，同一版本的 config/read 帶本專案 cwd，讀到 on-request / user。
3. 回覆列出本專案 .codex 設定層，確認設定確實載入。
4. sandbox_mode 修改前後相同；設定檔解析通過。
5. 核對只啟動臨時設定讀取程序，沒有建立對話或執行代理工作，完成後已結束。
6. 全部研究資料仍在原位，沒有重試被拒絕的刪除。

## 目前仍待完成

當前這一輪的權限是啟動時由主程式提供的 never；修改磁碟設定不能替換已提供給這一輪的權限。因此「設定讀取通過」不等於「目前對話已可提出核准」，也不等於內建刪除限制已解除。

下一步須讓目前對話重新載入，或由使用者在桌面的對話權限控制選擇可人工核准的模式。恢復工作時先核對新的有效權限；只有正式核准或放行後，才處理單一已完整封存並再次核對的目錄。若仍直接回覆 blocked by policy，需保留具體拒絕紀錄，不能以其他執行方式繞過。

重新載入這個對話不需要停止研究訓練。本次沒有關閉或重啟桌面程式。

## 證據

H:/GMM_2_Final_Archive/operation_logs/Storage_Migration_20260926/

- config_effective_before.json
- config_effective_after.json
- project_permission_routing_fix.json
- read_effective_permission_config.py

## 官方依據

[專案設定優先順序與核准設定](https://learn.chatgpt.com/docs/config-file/config-basic)

[config/read 設定讀取](https://learn.chatgpt.com/docs/app-server)

[核准設定不會改變內建限制或既有安全邊界](https://learn.chatgpt.com/docs/config-file/config-reference)


## 使用者返回對話後的實際核對

2026-09-26 14:42:55 +08:00 開始的新一輪仍為 approval_policy=never、sandbox=danger-full-access；桌面日誌同時列出 resolvedApprovalPolicy=never、useAppServerPermissionDefault=true。證據已保存至 permission_activation_check_after_continue.json。

先前建議切換至其他對話再返回並未生效，不能再將此步驟當作已驗證的修正方式。磁碟設定讀取通過，既有對話的有效設定仍未更新。

官方明確支援的入口是桌面輸入框下方的權限控制，選 Ask for approval（要求核准）。必須由介面把新權限送給目前對話；當前工具沒有可代替使用者設定此控制的功能。等待這個設定確認前，不重試被拒絕的刪除。

[官方權限模式與控制位置](https://learn.chatgpt.com/docs/permission-modes?translationFallback=zh-Hant)


## 使用者選擇 Ask for approval 後

2026-09-26 14:44:35 +08:00 的 thread_settings_applied 已為 on-request / user / :workspace，確認對話權限切換送達。此時正在執行的一輪仍有 14:42:55 開始時的 turn_context=never，不能把對話設定更新等同於已證明本輪命令使用新設定。

R53 原件及封存副本的精確檔案集、大小、修改時間重核通過；121 檔 D 保留內容再次核對通過。R56 四個目錄及 23 檔保留內容同樣通過。目前 R148v2 使用 R148 的獨立 payload，沒有本批來源交集。

同一個原生 R53 移除命令重試一次，仍在建立程序前被拒絕，來源完整保留，回收 0 bytes。證據在 docs/operations/storage_execution_20260926/R53_retry_after_user_permission_switch.json。沒有改用其他刪除方式。

需本輪結束後，在下一輪先確認 turn_context 已為 on-request，才能進一步驗證新的有效執行設定。不能僅憑本輪拒絕，就斷言人工核准模式下仍一定禁止刪除。使用者不需再切換權限或再次重新開啟對話。


## 最終實際解決結果

新一輪已切換可人工核准模式；正式 require_escalated 請求獲使用者核准後，與先前相同的 R53 原生移除命令成功。剩餘 18 個目錄亦按正式核准移除。這證明先前拒絕不是任何情況下都不可刪除的絕對禁止；可以透過正式核准途徑完成。沒有停用保護或新增寬泛刪除免審規則。此前對具體內部分支的推斷仍不作程式內部已證明的主張。

R53/R56 本批封存與精簡完成。完整移除後核對記錄見 storage_execution_20260926/post_cleanup_verification.json。
