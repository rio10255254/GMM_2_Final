# R32 Sandbox

## 概覽 / Overview

這裡是 `Round32` 的獨立實驗區。  
This directory is the isolated execution surface for `Round32`.

這個 sandbox 的目的，是把 `R32` 專用的訓練、audit、runtime、compare 流程和 root shared mainline 分開，避免實驗性變更重新混回共用主線。  
The sandbox exists to keep `R32`-specific training, audit, runtime, and compare logic separate from the root shared mainline, so experimental changes do not leak back into the stable workflow.

## 原則 / Operating Principles

- `R32` 不再依賴 root shared 主線的 `AutoTuneTrain.py`、`ProcessProbeAudit.py`、shared output monitor。  
- `R32` no longer depends on the root shared versions of `AutoTuneTrain.py`, `ProcessProbeAudit.py`, or the shared output monitor.
- root `Model/` 應維持 `R26 / R30 / shared stable workflow` 的乾淨狀態。  
- The root `Model/` directory should stay clean and reflect the `R26 / R30 / shared stable workflow`.
- `R32` 自己的訓練、profile、audit、launcher、monitor、status 都放在這個 sandbox 內。  
- `R32` keeps its own training, profiles, audits, launchers, monitors, and status files inside this sandbox.

## 2026-03-20 現況 / 2026-03-20 Truth

- `R32` internal 鏈已完成。  
- The internal `R32` chain is complete.
- internal winner：`r32_real_eq_finetune`。  
- The internal winner is `r32_real_eq_finetune`.
- canonical runtime state：`Experiments/R32Sandbox/runtime/R32_STATUS.md`。  
- The canonical runtime truth lives in `Experiments/R32Sandbox/runtime/R32_STATUS.md`.
- canonical decision：`Experiments/R32Sandbox/reports/ROUND32_DOMAIN_CAPACITY_DECISION_20260319_183614.md`。  
- The canonical decision memo lives in `Experiments/R32Sandbox/reports/ROUND32_DOMAIN_CAPACITY_DECISION_20260319_183614.md`.
- external compare status：`completed / FAIL`。  
- External compare has completed and the verdict is `FAIL`.
- final verdict：`r32_real_eq_finetune` 不能升級 baseline。  
- Final verdict: `r32_real_eq_finetune` cannot be promoted to baseline.
- next step：若續做 `R32`，必須另立新 sandbox branch / 新機制。  
- Next step: if `R32` continues, it must move to a new sandbox branch or a new mechanism.

## 主要入口 / Main Entry Points

### 訓練與流程 / Training and Workflow

- 訓練腳本：`Experiments/R32Sandbox/Model/train_r32.py`  
- Training script: `Experiments/R32Sandbox/Model/train_r32.py`
- profile / autotune：`Experiments/R32Sandbox/Model/profiles_r32.py`、`Experiments/R32Sandbox/Model/autotune_r32.py`  
- Profile / autotune: `Experiments/R32Sandbox/Model/profiles_r32.py` and `Experiments/R32Sandbox/Model/autotune_r32.py`
- audit：`Experiments/R32Sandbox/Model/process_probe_audit_r32.py`  
- Audit: `Experiments/R32Sandbox/Model/process_probe_audit_r32.py`

### 啟動與監看 / Launch and Monitoring

- 啟動腳本：`Experiments/R32Sandbox/Tools/start_r32_real_eq.ps1`  
- Launch script: `Experiments/R32Sandbox/Tools/start_r32_real_eq.ps1`
- 前景監看：`Experiments/R32Sandbox/Tools/open_r32_output_window.ps1`  
- Foreground monitor: `Experiments/R32Sandbox/Tools/open_r32_output_window.ps1`

### Runtime 狀態 / Runtime Status

- runtime 檔案：`Experiments/R32Sandbox/runtime/R32_STATUS.json`、`Experiments/R32Sandbox/runtime/R32_STATUS.md`  
- Runtime files: `Experiments/R32Sandbox/runtime/R32_STATUS.json` and `Experiments/R32Sandbox/runtime/R32_STATUS.md`

## 共用資產 / Shared Assets

這個 sandbox 仍共用以下 root 資源：  
This sandbox still shares the following root-level assets:

- root `Model/` 的穩定 backbone / utils。  
- The stable backbone and utilities in root `Model/`.
- root `Training_Data/`。  
- The root `Training_Data/`.
- root `PSF_Fitting/`。  
- The root `PSF_Fitting/`.
- root baseline checkpoint（例如 `R30 / r30_b1_dironly`）。  
- Root baseline checkpoints such as `R30 / r30_b1_dironly`.

## 輸出位置 / Output Locations

- sandbox 執行狀態寫到 `Experiments/R32Sandbox/runtime/`。  
- Sandbox runtime state is written to `Experiments/R32Sandbox/runtime/`.
- sandbox 訓練輸出寫到 `Experiments/R32Sandbox/artifacts/`。  
- Sandbox training outputs are written to `Experiments/R32Sandbox/artifacts/`.
- sandbox 報告寫到 `Experiments/R32Sandbox/reports/`。  
- Sandbox reports are written to `Experiments/R32Sandbox/reports/`.
