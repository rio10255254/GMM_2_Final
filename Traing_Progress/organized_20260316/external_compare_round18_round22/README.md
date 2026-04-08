# External GMF Three-Way Comparison: Round18 vs Round22

建立日期：2026-03-16

## 目的

Round22 通過了 calibrated internal pairmix gate，但 internal 通過 ≠ external GMF 通過。
本比較用 external GMF 作最終裁定，同時解決 stepguard vs hold 的 tie-break。

## 三個 Checkpoint

| 標籤 | Checkpoint 路徑 |
|------|----------------|
| round18_baseline | `organized_20260313\round18\selected\runs\training_progress_GESR_v1_v5_ST8_SWP_r18eh_20260313_141756\weights\best_tradeoff.pth.tar` |
| round22_stepguard | `organized_20260315\round22\selected\runs\training_progress_GESR_v1_v5_ST0p8_SWP_r22ps_20260315_225625\weights\best_tradeoff.pth.tar` |
| round22_hold | `organized_20260315\round22\archive\runs\training_progress_GESR_v1_v5_ST0p8_SWP_r22ph_20260315_225256\weights\best_tradeoff.pth.tar` |

## Internal Gate 指標（Round22）

| Checkpoint | center_err (0.8px) | step_err (0.8px) | 備注 |
|------------|-------------------|-----------------|------|
| round18_baseline | 0.8574 | 0.2854 | 舊基線 |
| round22_stepguard | 0.1845 | 0.0657 | formal selected，step-first 決策鏈 |
| round22_hold | 0.1508 | 0.0768 | raw mid-only 更強 center |

## 三個資料集

- `Pitch1um_Y_100`（1um / 8px，大尺度）
- `Pitch0.1um_Y_60`（0.1um / 0.8px，主戰場）
- `Pitch0.01um_Y_40`（0.01um / 0.08px，次要 guard）

## 執行流程

### Step 1：Recon（三顆 × 各 3 datasets）

```powershell
# Round18 baseline
powershell.exe -File "D:\GMM_2_Final\Tools\RunRepresentativeExternalRecon.ps1" `
    -WeightsPath "D:\GMM_2_Final\Traing_Progress\organized_20260313\round18\selected\runs\training_progress_GESR_v1_v5_ST8_SWP_r18eh_20260313_141756\weights\best_tradeoff.pth.tar" `
    -ReconRoot "D:\GMM_2_Final\Traing_Progress\organized_20260316\external_compare_round18_round22\round18_baseline\reconstructions"

# Round22 stepguard
powershell.exe -File "D:\GMM_2_Final\Tools\RunRepresentativeExternalRecon.ps1" `
    -WeightsPath "D:\GMM_2_Final\Traing_Progress\organized_20260315\round22\selected\runs\training_progress_GESR_v1_v5_ST0p8_SWP_r22ps_20260315_225625\weights\best_tradeoff.pth.tar" `
    -ReconRoot "D:\GMM_2_Final\Traing_Progress\organized_20260316\external_compare_round18_round22\round22_stepguard\reconstructions"

# Round22 hold
powershell.exe -File "D:\GMM_2_Final\Tools\RunRepresentativeExternalRecon.ps1" `
    -WeightsPath "D:\GMM_2_Final\Traing_Progress\organized_20260315\round22\archive\runs\training_progress_GESR_v1_v5_ST0p8_SWP_r22ph_20260315_225256\weights\best_tradeoff.pth.tar" `
    -ReconRoot "D:\GMM_2_Final\Traing_Progress\organized_20260316\external_compare_round18_round22\round22_hold\reconstructions"
```

### Step 2：GMF（由使用者執行）

每顆模型 × 三個資料集 → 輸出到各自的 `gmf_results/raw/pitch*/GMF_score.txt`

### Step 3：比較報告

Claude 讀取 9 份 `GMF_score.txt` → 產出 `reports/EXTERNAL_COMPARE_R18_R22_SUMMARY.md`

## 決策規則

| 外部結果 | 行動 |
|---------|------|
| stepguard 最優 | 升級 current adopted model 為 Round22 stepguard |
| hold 最優 | 改 formal selected artifact 為 hold |
| 兩者都不優於 Round18 | 不升級；回頭分析 internal/external mismatch |

## 驗收標準

recon 後：每顆模型都有 3 個資料集的 output 目錄 + `batch_manifest.json`
GMF 後：3 顆 × 3 尺度共 9 份 `GMF_score.txt` 全部存在，缺任何一份不進最終判讀
