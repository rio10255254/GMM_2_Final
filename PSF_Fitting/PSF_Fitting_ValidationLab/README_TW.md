# PSF Fitting ValidationLab

這個資料夾最初是 `HDR_fitting_2D_WholeFOV.m` 的獨立驗證沙盒，只在 subset 上重跑 Whole-FOV 2D PSF fitting，不修改任何原始流程。
目前其中收斂出的合理版流程已經升格為正式主線；本資料夾保留作為驗證、比較與歷史依據。
`outputs/reports/` 內的文字多數應視為「升格前的驗證快照」，正式日常入口與最新說明以 repo 根目錄 `PSF_Fitting/README.md` 為準。

## 目標

驗證兩個可疑點：

1. raw/GT 預對齊是否能消除 fitted PSF 的共同偏移。
2. 放開 tilt 自由度是否能消除共同偏移或改善貼界。

## 目錄

- `run_validation_lab.ps1`
  - PowerShell 一鍵入口，預設呼叫 MATLAB 跑完整最小對照組。
- `run_reasonable_fit.ps1`
  - 直接執行目前建議的合理版 Whole-FOV 擬合流程。
- `scripts/HDR_fitting_2D_WholeFOV_reasonable_v1.m`
  - 目前建議使用的合理版擬合入口，預設採用 `warm_start + refined pre_alignment (0.25 px) + tilt locked`。
- `scripts/vlab_get_experiment_configs.m`
  - 產生 baseline、整數 pre_alignment、細化 pre_alignment、tilt 對照等實驗設定。
- `scripts/vlab_run_validation_lab.m`
  - MATLAB 主入口，負責 subset fitting、輸出、比較表與報告。
- `scripts/vlab_aggregate_existing_results.m`
  - 從既有 `batch_results.csv` 重建 comparison、summary、recommendation 與 aggregate figures，會自動忽略未完成實驗。
- `outputs/experiments/<experiment_name>/`
  - 每組實驗的 `batch_results.csv`、`PSF_fitted_2D_FOVstack.mat`、`experiment_config.json`、`loss_histories.mat`。
- `outputs/figures/`
  - 偏移比較圖與 fval/iterations 比較圖。
- `outputs/reports/`
  - `validation_summary_tw.md`、`next_recommendation_tw.md`。
- `outputs/tables/`
  - `experiment_comparison.csv`。
- `../tests/matlab/validationlab/`
  - ValidationLab 相關 smoke tests 已統一集中於根目錄 `tests/`，不再散落於 `scripts/`。

## 預設實驗

預設 subset：`fi = [1, 56, 60, 100]`

- `baseline_subset`
  - `warm_start = on`
  - `pre_alignment = off`
  - `lock_tilt = on`
- `alignment_subset`
  - `warm_start = on`
  - `pre_alignment = on`
  - `lock_tilt = on`
- `tilt_subset`
  - `warm_start = on`
  - `pre_alignment = off`
  - `lock_tilt = off`
- `alignment_tilt_subset`
  - `warm_start = on`
  - `pre_alignment = on`
  - `lock_tilt = off`

## 重新執行

PowerShell：

```powershell
Set-Location PSF_Fitting/PSF_Fitting_ValidationLab
.\run_validation_lab.ps1
```

直接跑目前合理版 full100：

```powershell
Set-Location PSF_Fitting/PSF_Fitting_ValidationLab
.\run_reasonable_fit.ps1
```

只跑特定子集：

```powershell
.\run_validation_lab.ps1 -SubsetIndices 1,56,60
```

只跑特定實驗：

```powershell
.\run_validation_lab.ps1 -ExperimentNames baseline_subset,alignment_subset
```

跑 16 點代表子集：

```powershell
.\run_validation_lab.ps1 -ProfileName rep16 -ExperimentNames baseline_rep16,alignment_rep16,alignment_subpixel_rep16,alignment_quarter_rep16,alignment_tilt_rep16
```

只重跑聚合：

```powershell
.\run_validation_lab.ps1 -AggregateOnly
```

若只想聚合部分已完成實驗：

```powershell
.\run_validation_lab.ps1 -AggregateOnly -ExperimentNames baseline_subset,alignment_subset,tilt_subset
```

## 輸出重點

- `outputs/experiments/*/batch_results.csv`
  - 每張 subset image 的 fval、iterations、預對齊位移、peak/centroid offset、邊界指標。
- `outputs/tables/experiment_comparison.csv`
  - 各組平均 offset、貼界、fval、iterations 對照。
- `outputs/reports/validation_summary_tw.md`
  - 繁中摘要，直接回答哪組最能消除共同偏移與避免貼界。
- `outputs/reports/next_recommendation_tw.md`
  - 下一步正式化建議。
- `outputs/reports/candidate_flow_tw.md`
  - 目前正式候選流程與原流程差異、以及為什麼暫時維持 `tilt locked`。

## 目前收斂結論

- 在代表性 16 點子集上，目前最佳候選是 `alignment_quarter_rep16`。
- 也就是：
  - `warm_start = on`
  - `pre_alignment = on`
  - `prealign_step = 0.25`
  - `lock_tilt = on`
- 目前證據顯示，先把 raw/GT 預對齊做細化，比直接放開 tilt 更有價值。
- `0.125px` 級別的更細步距目前只通過了單張 smoke，尚未作為正式候選；目前以 `0.25px` 作為穩定且可重現的預設值。
- full100 合理版結果已產生於 `outputs/final_candidate_full100/`，摘要在 `outputs/reports/final_candidate_full100_summary_tw.md`。
- 正式主線現在由 repo 根目錄的 `HDR_fitting_2D_WholeFOV.m` 與 `HDR_fitting_2D_WholeFOV_impl.m` 接手；ValidationLab 不再是日常主入口。

## 中斷後處理

如果 MATLAB fitting 中途被中斷，但某些實驗資料夾內已經有完整 `batch_results.csv`，可以直接執行：

```powershell
.\run_validation_lab.ps1 -AggregateOnly
```

這會重新掃描 `outputs/experiments/*/batch_results.csv`，只用已完成的實驗重建 comparison、summary、recommendation 與 aggregate figures，不需要重跑已完成的 fitting。
