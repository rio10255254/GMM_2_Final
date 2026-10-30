# organized_20260310 歷史批次清單

Last updated: 2026-08-01

- 角色：代表模型多尺度外部驗證、SeqVal 與 crossscale 比較、uint16 microstep 探測的歷史批次。
- 主要判讀：大尺度與中尺度當時較可用，0.08 px 微步仍不穩；這是研究過程證據，不是現行正式基準。
- 現行判讀：以 `PROJECT_STATE.md` 與 `ESTIMATOR_POLICY.json` 為準。

封存前完整批次共 928 個檔案、2,351,401,480 bytes（2.190 GiB），已逐檔核對保存到：

`H:\GMM_2_Final_Archive\legacy\organized_20260310\20260801_full_history\snapshot`

D 槽保留根層 precision-fix 報告、pending/debug 的小型歷史、從三組驗證抽出的 38 份原始 GMF 分數、分析結果、比較摘要與重建清單、本清單及恢復說明。大型 `external_validation/` 影像與完整執行輸出由 H 槽保存。

執行結果：`external_validation/` 已移除，實際回收 2.191 GiB；根層報告、pending/debug 小型歷史與 38 份核心證據均保留。H 槽在刪除後再次核對 PASS。
