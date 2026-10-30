# Diagnostics

這個目錄承載 `round20` 之後、`Round21` 之前的診斷工作。

角色：

- 不產生新 deploy 模型
- 不做 external recon
- 只回答「下一步該走哪個技術分支」

目前最重要入口：

- matrix summary:
  `Experiments/Legacy/organized_20260314/diagnostics/DIAGNOSTIC_MATRIX_SUMMARY_20260314_232403.md`
- branch decision:
  `Experiments/Legacy/organized_20260314/diagnostics/ROUND21_BRANCH_DECISION.md`

truth source 說明：

- 這裡的 absolute center 真值不是從 raster 反推
- 而是從 `Training_Data\Data_Simulaion.py` 的 deterministic generator replay 直接重建

因此這裡回答的是：

- 現行幾何估計器相對於 synthetic truth 到底偏多少
- 偏差是在 clean / convolved 就出現，還是只在 SR 才出現

目前結論：

- `Branch E: estimator-side`

archive 規則：

- smoke 與早期錯誤判讀版本一律收進 `archive`
- 只保留最新正式 matrix summary / decision memo 在根層
