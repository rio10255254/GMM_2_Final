# R32 Sandbox

這裡是 `Round32` 的獨立實驗區。

原則：

- `R32` 不再依賴 root shared 主線的 `AutoTuneTrain.py`、`ProcessProbeAudit.py`、shared output monitor
- root `Model/` 應維持 `R26 / R30 / shared stable workflow` 的乾淨狀態
- `R32` 自己的訓練、profile、audit、launcher、monitor、status 都放在這個 sandbox 內

## 2026-03-20 Truth

- `R32` internal 鏈已完成
- internal winner：`r32_real_eq_finetune`
- canonical runtime state：
  `Experiments/R32Sandbox/runtime/R32_STATUS.md`
- canonical decision：
  `Experiments/R32Sandbox/reports/ROUND32_DOMAIN_CAPACITY_DECISION_20260319_183614.md`
- external compare status：
  `completed / FAIL`
- final verdict：
  `r32_real_eq_finetune` 不能升級 baseline
- next step：
  若續做 `R32`，必須另立新 sandbox branch / 新機制

## 入口

- 訓練腳本：
  - `Experiments/R32Sandbox/Model/train_r32.py`
- profile / autotune：
  - `Experiments/R32Sandbox/Model/profiles_r32.py`
  - `Experiments/R32Sandbox/Model/autotune_r32.py`
- audit：
  - `Experiments/R32Sandbox/Model/process_probe_audit_r32.py`
- 啟動：
  - `Experiments/R32Sandbox/Tools/start_r32_real_eq.ps1`
- 前景監看：
  - `Experiments/R32Sandbox/Tools/open_r32_output_window.ps1`
- runtime status：
  - `Experiments/R32Sandbox/runtime/R32_STATUS.json`
  - `Experiments/R32Sandbox/runtime/R32_STATUS.md`

## 共用資產

這個 sandbox 仍共用：

- root `Model/` 的穩定 backbone / utils
- root `Training_Data/`
- root `PSF_Fitting/`
- root baseline checkpoint（例如 `R30 / r30_b1_dironly`）

## 輸出

- sandbox 執行狀態寫到 `Experiments/R32Sandbox/runtime/`
- sandbox 訓練輸出寫到 `Experiments/R32Sandbox/artifacts/`
- sandbox 報告寫到 `Experiments/R32Sandbox/reports/`
