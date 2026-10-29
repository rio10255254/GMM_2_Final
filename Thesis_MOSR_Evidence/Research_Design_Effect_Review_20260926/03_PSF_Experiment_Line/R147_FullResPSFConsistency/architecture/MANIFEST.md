# R147 來源、模型與執行身分

- 類型：自包含研究對照。狀態：正式8192次訓練、930張實拍／8370圓、單張重播與最後稽核完成；2026-09-26內部診斷及歷史對照完成，改良設計提出但未開始新訓練。短步退步、直徑重拍改善，不升級正式基準。
- PSF：逐位元複製 R146 的研究版 25 顆銀行 `calibration/measured_psf_bank.npz`，SHA-256 `efc9d70d6427d82ba84f1371f71b6423f1491a815956412f8d6a627b72b1f843`；源 MAT 為 `PSF_Fitting/output/20260924_center9_psf/model_search/PSF_20260924_SEM_core_halo_25_RESEARCH.mat`，SHA-256 `0d85d63c08a943a56d6fd74d2ce250b0d656d1170e7ab185e95d2ff369a797e6`，保留 `research_only=1`。真實 SEM 外框用於 PSF 光學校準，從未作神經清晰答案。
- 資料：R146 相同的 768 清楚母場景、配對模糊、分組、逐場景 PSF 編號及雜訊。`data/manifest.json` 與 R146 逐位元相同；本輪只修改模型光學運算，沒有重新調資料。
- 模型：四次共享 U-Net 維持原影像／梯度／配對位移訓練目標；PSF 路徑改成原尺寸、中心對齊、固定 25 顆平均的成像一致性與有界回投。無逐張選擇器，通道增加兩個可檢查的原尺寸成像差訊號。初始物理步長 0.3、上限 0.8，從 40 組合成保留場景設定，未使用實拍評分挑值。
- 預先檢查：`results/native_psf_operator_validation.json`、`results/optical_step_preflight.json`、`results/preflight.json` 均通過；最終訓練來源鎖 `config/SOURCE_LOCK.json` 已建立。
- 正式驗證：固定 30 趟×31 張實拍、九顆圓和 PI 軸；R146 為主要對照，R145、R143、R140v2、RAW 為既有參照，原結果不改動。
- 最後模型SHA-256 `0e0c5a78d6fbb450a026289a177f7b5f50c10f6ea0564ab505382435af8ea4d0`。內部診斷收據 `results/internal_audit/verification.json`：4320筆階段圓、120筆修正分解、1134筆位移控制、810筆裁切、1134筆擾動、108筆R137格點控制、24筆作用範圍、14組實際訓練批次、768組祖源與原始陣列核對。30張末步浮點差0，階段位移獨立重算一致；原來源與評估鎖不變。
- D槽空間於2026-09-26恢復後，完整結果報告、圖表和驗證狀態由H槽逐檔核對同步至此正式入口；H槽驗證副本保留。磁碟滿載期間的保存點備份也在H槽 `training_run_initial_backup`，與D槽33檔逐檔相同。既有備份不刪除。
- D 槽保留程式與資料；正式訓練的執行檔案在 H 槽 `active_runs/R147_FullResPSFConsistency/training_run`，D 槽 `runs/formal_8192` 為其連結。搬移時逐檔 SHA-256 核對 33 檔；D 槽 `runs/formal_8192_local_verified_copy` 暫保留完整備份。從第 2944 次儲存點接續，未儲存的 2945–3047 次紀錄另存、並從儲存點重算。`results` 整體在 H 槽 `active_runs/R147_FullResPSFConsistency/results_root`，D 槽 `results` 為連結；其中影像、圓心和比較表各有獨立 H 槽資料夾。搬移四份前置結果逐檔 SHA-256 相同，兩份來源鎖搬移後複核通過。D 槽 `results_local_verified_copy` 暫保留原樣備份。無自動正式基準升級。
