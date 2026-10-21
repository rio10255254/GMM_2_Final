# R26 Legacy Empirical Baseline Manifest

這份文件記錄舊 PSF 與舊 formal deploy checkpoint，供歷史報告、基準比較與回溯使用。

## 身份

- 類型：`legacy empirical baseline`
- 用途：歷史最佳經驗值對照，不再是 current standard

## 固定 hash

| asset | path | sha256 |
|---|---|---|
| legacy PSF | `內部檔案\PSF_Fitting\Crop_circle_FreqFiltered\Fits\legacy_baseline\PSF_fitted_2D_FOVstack_legacy_empirical.mat` | `3AAB9CC1ED9EE0EB9C85227D026A3A8D86D0C035B8D06A46EB688551EFAE79CD` |
| legacy deploy checkpoint | `內部檔案\weights\legacy_baseline\r26_sm035_best_tradeoff_legacy_empirical.pth.tar` | `1057F98B9B074621F1D8E7AEAD3D51545D839C79008E35011433868CA7E78CB0` |
| seed checkpoint | `內部檔案\weights\r25_sw010_seed_best_tradeoff.pth.tar` | `0C48D0B3F160C6F776C6C722EAD6C839A939475198DA4D69F88399BA6F508A1C` |

## 說明

- 舊 baseline 被保留，是為了維持 historical provenance 與 compare 可追溯性。
- 這不代表舊 baseline 是錯誤資料；它代表的是先前的 empirical winning line。
- current standard 若改為新 PSF，舊 baseline 仍必須保留，而不是直接刪除。
