# PSF Formal Flow Audit

日期：2026-03-26

## 審核目的

在不覆寫目前 `D:\GMM_2_Final\PSF_Fitting\Crop_circle_FreqFiltered\Fits` 正式輸出的前提下，確認 root `PSF_Fitting/` 的正式流程是否存在明顯原理或執行層面的問題。

## 本次檢查範圍

### 1. 正式入口與 promoted config 是否一致

- `D:\GMM_2_Final\PSF_Fitting\HDR_fitting_2D_WholeFOV.m`
  - 目前只是 thin wrapper，直接呼叫 `HDR_fitting_2D_WholeFOV_impl()`
- `D:\GMM_2_Final\PSF_Fitting\HDR_fitting_2D_WholeFOV_impl.m`
  - 預設參數為：
    - `warm_start = true`
    - `pre_alignment = true`
    - `lock_tilt = true`
    - `prealign_search_step = 0.25`
    - `output_root = Crop_circle_FreqFiltered/Fits`
- `D:\GMM_2_Final\PSF_Fitting\Crop_circle_FreqFiltered\Fits\formal_config.json`
  - 與上面正式入口邏輯一致
  - 目前 formal candidate 來源仍指向 ValidationLab reasonable candidate

結論：formal entrypoint、formal_config 與 ValidationLab promotion 敘事一致，沒有看到「文件說一套、程式跑另一套」的直接矛盾。

### 2. Python 測試

執行：

```powershell
pytest D:\GMM_2_Final\PSF_Fitting\tests\python\test_report_analysis.py -q
```

結果：

- `6 passed in 1.80s`

### 3. ValidationLab aggregate only

執行：

```powershell
Set-Location D:\GMM_2_Final\PSF_Fitting\PSF_Fitting_ValidationLab
.\run_validation_lab.ps1 -AggregateOnly
```

結果：

- aggregate 成功重建 comparison / figures / reports
- `best_overall_experiment = alignment_quarter_rep16`
- `best_fval_experiment = alignment_quarter_rep16`

結論：ValidationLab 的既有實驗輸出可被重新聚合，promotion 所依賴的比較鏈沒有壞掉。

### 4. MATLAB smoke tests

執行：

```powershell
matlab -batch "cd('D:/GMM_2_Final/PSF_Fitting'); run('tests/run_matlab_smoke_tests.m')"
```

結果：

- `All MATLAB smoke tests completed.`
- 共完成 `11/11` 個 smoke tests

觀察：

- 過程中持續出現 BADS 的 bounds warning：
  - `Plausible lower/upper bounds PLB and/or PUB not specified. Using hard upper/lower bounds instead.`
- 這個 warning 在 smoke 測試內是可重現但不致 fail 的現象，目前看起來比較像既有設定提示，而不是 formal flow 中斷或輸出錯誤。

## 目前審核結論

1. **執行面沒有立刻看到 formal flow 壞掉。**
   - formal entrypoint 可正常呼叫
   - ValidationLab aggregate 可重建
   - Python tests 通過
   - MATLAB smoke tests 通過

2. **目前沒有足夠理由只因為「formal flow 會不會壞掉」就直接重跑 full100。**
   - 就 execution sanity 而言，現有正式流程目前站得住。

3. **但這不等於已證明新 formal PSF 對下游模型一定是好的。**
   - 下游模型在 Demo 單張上的退步，仍然是真實觀察。
   - 那個問題目前更像是「新 formal PSF + 舊 training recipe / checkpoint selection 的組合是否不合適」，而不是 `PSF_Fitting` formal pipeline 直接 crash 或明顯自相矛盾。

## 因此目前建議

- 暫時不要因為 execution panic 去覆寫 formal PSF。
- 先等待這次 external GMF 結果，確認下游退步是否也會出現在三尺度外部資料集。
- 如果之後要再往前追 PSF 原理問題，應優先檢查：
  - `D:\GMM_2_Final\PSF_Fitting\PSF_Fitting_ValidationLab\outputs\reports\candidate_flow_tw.md`
  - `D:\GMM_2_Final\PSF_Fitting\PSF_Fitting_ValidationLab\outputs\reports\validation_summary_tw.md`
  - `D:\GMM_2_Final\PSF_Fitting\HDR_fitting_2D_WholeFOV_impl.m`
  - `D:\GMM_2_Final\PSF_Fitting\PSF_Fitting_ValidationLab\scripts\HDR_fitting_2D_WholeFOV_reasonable_v1.m`

- 若未來真的要重來一次，建議先在 ValidationLab 或獨立 recheck output root 內重跑，不要直接覆寫 `Crop_circle_FreqFiltered/Fits`。
