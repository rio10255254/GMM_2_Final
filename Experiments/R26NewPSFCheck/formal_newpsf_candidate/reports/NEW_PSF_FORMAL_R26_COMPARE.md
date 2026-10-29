# New PSF Formal R26 Compare

日期：2026-03-27

## 比較對象

- legacy baseline
  - PSF: `3AAB9CC1ED9EE0EB9C85227D026A3A8D86D0C035B8D06A46EB688551EFAE79CD`
  - checkpoint: `1057F98B9B074621F1D8E7AEAD3D51545D839C79008E35011433868CA7E78CB0`
- current standard candidate
  - PSF: `BAFF1039744ED17CFFBA3D9F36A2535A7171BAC74E4B67669EDE412FB4B44F08`
  - checkpoint: `0D68897E2F649111ACAE7B59D46F77F1F48EF4A2E0FB32F14C8C5FFDF014FE50`

## Same-recipe 確認

這次 promote 不是 generic retrain 結果，而是沿用 `r26_sm035` 的 same-recipe pure control 線：

- seed 不變
- deterministic 不變
- selected stage subset 不變
- model scripts 不變
- 變更內容只限於 PSF 對應的 formal current-standard 資產

pure control 的核心結論仍成立：

- `old_recipe + old_psf`
- `old_recipe + new_centered_psf`

在 `epoch 10 / 20 / 40` 的單張指標幾乎重合，沒有重現先前 `recipe drift` 版本的崩壞。

## Package 使用面驗證

已完成以下 fresh 驗證：

- repo-tracked validation:
  - `pytest Experiments/R26NewPSFCheck/package_repro_validation/tests/test_r26_formal_package.py -q`
- `GeoEdge_R26_FormalTrain.ps1 -Action dry-run`
- `GeoEdge_R26_FormalInfer.ps1 -Action dry-run-demo`
- `GeoEdge_PackageSmokeTest.ps1 -InferenceSampleCount 1 -SkipTrain`
- local-only package policy guard:
  - `pytest Experiments/R26NewPSFCheck/package_policy_transition/tests/test_psf_policy_transition.py -q`
  - 此 guard 依賴本地 `_deployment_package` metadata，並未追蹤進 Git

結果：

- transition policy gate（local-only）：PASS
- package formal validation：PASS
- wrapper dry-run：PASS
- package smoke inference：PASS

smoke test 產出：

- demo:
  - `_deployment_package/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/輸出結果/推論結果/_smoketest_demo/reconstruct_progress_r26_sm035_best_tradeoff_in_input_subset_20260327_101759`
- custom:
  - `_deployment_package/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/輸出結果/推論結果/_smoketest_custom/reconstruct_progress_r26_sm035_best_tradeoff_in_input_subset_20260327_101759`

## 指標解讀

依 `pure_psf_control` 的正式解讀：

- 新 PSF 不是先前崩壞的充分原因
- 先前大退步應歸因於 `PSF 變更 + recipe drift`
- 在 same-recipe 條件下，新 PSF 沒有顯示出 clear breakage

本次 promotion 的標準不是「必須全面超越 legacy baseline」，而是：

- 新 PSF 在物理上較合理
- 使用面不壞
- same-recipe 下沒有重現崩壞

若有些微數值退步，視為可接受的 policy cost，而不是自動回退理由。

## Verdict

**Promote**

理由：

1. 研究原則已明確採 physics-first。
2. 新 PSF 有 same-recipe replacement checkpoint，不是 orphan file swap。
3. package 使用面與 validation 沒有壞。
4. legacy baseline 仍已完整保留，可供後續歷史比較與回溯。
