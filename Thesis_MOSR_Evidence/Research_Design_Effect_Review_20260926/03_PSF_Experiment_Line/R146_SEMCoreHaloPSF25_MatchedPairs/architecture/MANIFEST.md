# R146 來源與執行身分

- 類型：自包含研究對照；狀態：研究版 PSF、768 組配對、8192 次從零訓練、930 張實拍及 8370 顆圓量測完成，`results/final_audit.json` 通過；研究版 PSF 不升級正式用途。
- 指定 MAT：`PSF_Fitting/output/20260924_center9_psf/model_search/PSF_20260924_SEM_core_halo_25_RESEARCH.mat`，SHA-256 `0d85d63c08a943a56d6fd74d2ce250b0d656d1170e7ab185e95d2ff369a797e6`。檔案明記 `research_only=1`，本輪不提升它為正式 PSF。
- 來源檢查：`model_search/verification.json` 通過，25 顆 101×101 非負、單顆總和 1、峰值與強度重心置中；物面 0.1725 µm/像素，九顆 SEM 編號為 36、35、34／30、29、28／24、23、22。預先封存的 E 組六張照片、18 個留出圓外觀中，研究版均優於原 BADS 與單一高斯；同九顆實物，不是新樣品準確度證明。
- 本包銀行：`calibration/measured_psf_bank.npz`，由指定 MAT 列優先 5×5 安裝，SHA-256 `efc9d70d6427d82ba84f1371f71b6423f1491a815956412f8d6a627b72b1f843`。真實 SEM 外框用於光學 PSF 擬合，神經清晰答案維持合成場景。
- 對照：R145、R143 的 768 清晰母場景、分組及逐場景 PSF 索引固定；新銀行與它形成的模糊輸入為本輪變更。原模型架構與光學分支設定不修正。
- 最終模型保存點：`runs/formal_8192/checkpoints/step08192.pth`，SHA-256 `17807a1ff81df08f7d31a3de40d099a01ee33c96208048a659994902fc4a95c9`。`verify_package.py --mode infer-ready` 通過；單張推論與批次輸出逐值相同。
- 完整結果與限制：[實拍與合成結果](reports/R146_RESULTS.md)；[來源較好、量測退步的原因核對](reports/R146_CAUSAL_AUDIT.md)。`results/position_stability_followup.json`、`results/displacement_repeatability_intervals.json`、`results/diameter_shift_intervals.json` 保留完整趟次及逐顆分析。
- `results/data_training_chain_audit.json` 直接從指定 MAT 重做 768 組資料並核對全部 1536 張、8192 筆場景順序及最終權重；`results/epoch_noise_replay_audit.json` 另外抽查 21 個實際訓練批次的每輪雜訊。`results/edge_response_r145_r146.csv` 與 `results/edge_variability_audit.json` 保存全部 8370 顆圓的邊緣寬度和 30 趟波動。
- 固定實拍：相同 30 趟×31 張、九顆圓、PI 軸及相同 ACM／LSC 讀法。既有 RAW、R140v2、R143、R145 量測不改動。
- D 槽保留程式、資料、權重和表格；H 槽 `active_runs/R146_SEMCoreHaloPSF25_MatchedPairs/reconstruction` 保存 930 張浮點輸出與收據。無正式基準自動升級。
