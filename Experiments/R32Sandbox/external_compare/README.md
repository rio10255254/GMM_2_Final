# R32 External Compare

## 概覽 / Overview

這裡是 `R32 sandbox` 的 external GMF 驗證區。  
This directory is the external GMF validation surface for the `R32 sandbox`.

它的角色，是把 `R32` 的 external validation 固定在 sandbox 範圍內，而不是把流程重新寫回 root shared 主線。  
Its role is to keep `R32` external validation inside the sandbox boundary instead of pushing that workflow back into the root shared mainline.

## 目的 / Purpose

- 保持 `R32` 的 external validation 不回寫到 root shared 主線  
  Keep `R32` external validation out of the root shared mainline.
- 固定 `R30 / r30_b1_dironly` 當 baseline  
  Keep `R30 / r30_b1_dironly` as the baseline reference.
- 對 `Round32` internal winner 產生：  
  Produce the following for the `Round32` internal winner:
  - recon outputs
  - external GMF raw directories
  - compare reports

## 標準流程 / Standard Flow

### 1. 跑 recon / Run Reconstruction

```powershell
powershell.exe -File "Experiments/R32Sandbox/Tools/run_r32_external_recon.ps1"
```

### 2. 執行外部 GMF scoring / Run External GMF Scoring

用固定的外部 GMF 工具對三個 pitch reconstruction 輸出做 scoring。  
Use the fixed external GMF tool to score the three pitch reconstruction outputs.

### 3. 放置 `GMF_score.txt` / Place `GMF_score.txt`

將 `GMF_score.txt` 放到以下位置：  
Place `GMF_score.txt` into the following locations:

- `Experiments/R32Sandbox/external_compare<candidate>\gmf_results\raw\<candidate>\pitch8px\GMF_score.txt`
- `Experiments/R32Sandbox/external_compare<candidate>\gmf_results\raw\<candidate>\pitch0p8px\GMF_score.txt`
- `Experiments/R32Sandbox/external_compare<candidate>\gmf_results\raw\<candidate>\pitch0p08px\GMF_score.txt`

### 4. 產生 compare 報告 / Generate Compare Report

```powershell
C:\Users\Rio\anaconda3\python.exe "Experiments/R32Sandbox/Model/external_gmf_round32_compare.py"
```

## 正式輸出 / Formal Outputs

- compare markdown  
  `Experiments/R32Sandbox/reports/ROUND32_EXTERNAL_COMPARE.md`
- compare json  
  `Experiments/R32Sandbox/reports/ROUND32_EXTERNAL_COMPARE.json`

## 2026-03-20 現況 / 2026-03-20 Current State

- selected candidate：`r32_real_eq_finetune`  
  Selected candidate: `r32_real_eq_finetune`
- selected checkpoint：  
  `Experiments/R32Sandbox/artifacts/training_progress_GESR_v1_v5_ST0p8_SWP_r32realeq_20260319_165431/weights/best_tradeoff.pth.tar`
- three pitch recon outputs：已生成  
  The three pitch reconstruction outputs have already been generated.
- compare status：`completed`  
  Compare status is `completed`.
- final verdict：`FAIL`  
  Final verdict is `FAIL`.

### 結果摘要 / Result Summary

- `8px`: `0.205193 -> 0.319667`, delta `+0.114475`
- `0.8px`: `0.167862 -> 0.331821`, delta `+0.163960`, `+97.7%`
- `0.08px`: `0.157720 -> 0.230119`, delta `+0.072399`
- `0.8px` outlier filtered 仍為 `0.303349`  
  The `0.8px` outlier-filtered result still remains `0.303349`.
- baseline decision：`Round30 / r30_b1_dironly` unchanged  
  Baseline decision: `Round30 / r30_b1_dironly` remains unchanged.
- next step：若續做 `R32`，需新分支 / 新機制，不延用這個 winner  
  Next step: if `R32` continues, it must use a new branch or a new mechanism rather than reusing this winner.

## 注意 / Notes

- repo 內目前只有 `recon -> compare` 是可自動化的  
  Inside the repo, only the `recon -> compare` part is currently automated.
- `GMF_score.txt` 仍來自固定外部 GMF 工具，不是 repo 內腳本直接生成  
  `GMF_score.txt` still comes from the fixed external GMF tool and is not generated directly by repo scripts.
