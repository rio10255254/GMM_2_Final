# PSF_Fitting 測試說明

此資料夾集中 `PSF_Fitting` 專案自有的測試與測試產物。

## 結構

- `matlab/wholefov/`
  - Whole-FOV 正式入口與相容輸出的 smoke tests。
- `matlab/validationlab/`
  - ValidationLab 與 reasonable/candidate 流程的 smoke tests。
- `python/`
  - `PSF_Report_Helper` 的 Python 單元測試。
- `artifacts/`
  - MATLAB smoke tests 產生的最小輸出樣本。
- `run_matlab_smoke_tests.m`
  - 一次加入 `tests/matlab/` 路徑並依序執行 MATLAB smoke tests。

## 執行方式

在 `D:\GMM_2_Final\PSF_Fitting` 下執行：

### MATLAB smoke tests

```powershell
matlab -batch "cd('D:/GMM_2_Final/PSF_Fitting'); run('tests/run_matlab_smoke_tests.m')"
```

注意：`run_matlab_smoke_tests.m` 會包含少量真正執行 Whole-FOV fitting 的 smoke tests，通常需要數分鐘，並不屬於瞬間完成的檢查。

### Python tests

```powershell
pytest tests/python/test_report_analysis.py -q
```

## 原則

- 只集中本專案自行撰寫的測試。
- 第三方套件（例如 `bads-1.1.3`）內建測試不搬移、不改動。
- 測試生成的最小 artifact 統一留在 `tests/artifacts/`，避免散落在主流程資料夾。
