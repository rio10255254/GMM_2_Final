# R32 External Compare

這裡是 `R32 sandbox` 的 external GMF 驗證區。

## 目的

- 保持 `R32` 的 external validation 不回寫到 root shared 主線
- 固定 `R30 / r30_b1_dironly` 當 baseline
- 對 `Round32` internal winner 產生：
  - recon outputs
  - external GMF raw 目錄
  - compare 報告

## 標準流程

1. 跑 recon

```powershell
powershell.exe -File "D:\GMM_2_Final\Experiments\R32Sandbox\Tools\run_r32_external_recon.ps1"
```

2. 用外部 GMF 工具對三個 pitch reconstruction 輸出做 scoring

3. 把 `GMF_score.txt` 放進：

- `D:\GMM_2_Final\Experiments\R32Sandbox\external_compare\<candidate>\gmf_results\raw\<candidate>\pitch8px\GMF_score.txt`
- `D:\GMM_2_Final\Experiments\R32Sandbox\external_compare\<candidate>\gmf_results\raw\<candidate>\pitch0p8px\GMF_score.txt`
- `D:\GMM_2_Final\Experiments\R32Sandbox\external_compare\<candidate>\gmf_results\raw\<candidate>\pitch0p08px\GMF_score.txt`

4. 產生 compare 報告

```powershell
C:\Users\Rio\anaconda3\python.exe "D:\GMM_2_Final\Experiments\R32Sandbox\Model\external_gmf_round32_compare.py"
```

## 正式輸出

- compare markdown:
  - `D:\GMM_2_Final\Experiments\R32Sandbox\reports\ROUND32_EXTERNAL_COMPARE.md`
- compare json:
  - `D:\GMM_2_Final\Experiments\R32Sandbox\reports\ROUND32_EXTERNAL_COMPARE.json`

## 2026-03-20 Current State

- selected candidate：`r32_real_eq_finetune`
- selected checkpoint：
  `D:\GMM_2_Final\Experiments\R32Sandbox\artifacts\training_progress_GESR_v1_v5_ST0p8_SWP_r32realeq_20260319_165431\weights\best_tradeoff.pth.tar`
- three pitch recon outputs：已生成
- compare status：`completed`
- final verdict：`FAIL`
- result summary：
  - `8px`: `0.205193 -> 0.319667`, delta `+0.114475`
  - `0.8px`: `0.167862 -> 0.331821`, delta `+0.163960`, `+97.7%`
  - `0.08px`: `0.157720 -> 0.230119`, delta `+0.072399`
  - `0.8px` outlier filtered 仍為 `0.303349`
- baseline decision：`Round30 / r30_b1_dironly` unchanged
- next step：若續做 `R32`，需新分支 / 新機制，不延用這個 winner

## 注意

- repo 內目前只有 `recon -> compare` 是可自動化的。
- `GMF_score.txt` 仍來自固定外部 GMF 工具，不是 repo 內腳本直接生成。
