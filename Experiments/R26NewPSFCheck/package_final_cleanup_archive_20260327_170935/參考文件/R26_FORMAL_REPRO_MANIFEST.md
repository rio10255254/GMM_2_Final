# R26 Formal Reproduction Manifest

這份文件定義 package 內目前採用的 **current standard** 與 **baseline 重新訓練預設**：正式 `R26 / r26_sm035` 資產、新的物理標準 PSF，以及完整重新訓練時使用的 baseline recipe。

## 目前標準定位

- winner: `r26_sm035`
- source_winner_kind: `sweep`
- package_train_kind: `full_train_baseline`
- model_name: `GESR_v1_v5_ST0p8_SWP_r26sm035`
- source report:
  - `D:\GMM_2_Final\Traing_Progress\auto_tune_reports\auto_tune_report_20260316_185417.json`

## 固定 hash

| asset | package path | sha256 |
|---|---|---|
| current-standard PSF | `內部檔案\PSF_Fitting\Crop_circle_FreqFiltered\Fits\PSF_fitted_2D_FOVstack.mat` | `BAFF1039744ED17CFFBA3D9F36A2535A7171BAC74E4B67669EDE412FB4B44F08` |
| current-standard deployed checkpoint | `內部檔案\weights\r26_sm035_best_tradeoff.pth.tar` | `0D68897E2F649111ACAE7B59D46F77F1F48EF4A2E0FB32F14C8C5FFDF014FE50` |
| formal seed checkpoint | `內部檔案\weights\r25_sw010_seed_best_tradeoff.pth.tar` | `0C48D0B3F160C6F776C6C722EAD6C839A939475198DA4D69F88399BA6F508A1C` |

## 固定 seed 與 determinism

- seed: `1261620`
- deterministic: `true`

## 正式 stage subset

這份 package 不攜帶整個歷史 `generated*` 全量資料，而只攜帶正式 `r26_sm035` 實際依賴的 stage 子集：

- `stage_08_annulus_focus`
- `stage_09_annulus_non_overlap`
- `stage_10_annulus_overlap`
- `stage_14_annulus_edge_defect_focus`
- `stage_15_annulus_sparse_clean`
- `stage_16_annulus_sparse_defect_clean`
- `stage_23_annulus_gmf_sequence_mid_clean`
- `stage_24_annulus_gmf_sequence_mid_defect`
- `stage_27_annulus_gmf_sequence_midwide_clean`
- `stage_28_annulus_gmf_sequence_midwide_defect`

來源根路徑：

- `內部檔案\Training_Data\generated_convolved\`
- `內部檔案\Training_Data\generated\`

## 固定 recipe 檔

- `內部檔案\formal_r26_recipe.json`

這份 JSON 會固定記錄：

- current-standard PSF 路徑
- seed checkpoint 路徑
- current-standard deployed checkpoint 路徑
- formal selected stages
- baseline 訓練 hyperparameters

## 正式入口

- 推論：
  - `RUN_DEMO_INFERENCE.bat`
  - `RUN_CUSTOM_INFERENCE.bat`
- baseline 完整重新訓練：
  - `RUN_FULL_TRAIN.bat`
- smoke test：
  - `RUN_QUICK_TRAIN.bat`

## 重要原則

- `RUN_FULL_TRAIN.bat` 是基於歷史 `R26 / r26_sm035` baseline 的完整重新訓練，不是 12-epoch sweep replay
- `RUN_QUICK_TRAIN.bat` 是 smoke，不得當成正式完整訓練效果
- package 內只保留 current-standard 正式資產
