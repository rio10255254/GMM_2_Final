# R26 New PSF Check

## 目的

這個 sandbox 用來承接兩件事：

1. 以「新 PSF 擬合結果重訓出的最佳權重」重建外部三尺度資料集，供外部 GMF 驗證。
2. 在不污染 R26 交付封包的前提下，對 root `PSF_Fitting/` 的正式流程做一次可追溯審核。

## 為什麼不直接在交付封包內做

- `D:\GMM_2_Final\_deployment_package\GeoEdge_R26_正式交付版\GeoEdge_R26_使用包` 應保留交付封包語意。
- 這次 external compare 與 PSF recheck 都屬於根專案的研究/驗證工作，不應再把新輸出混進交付包主結構。
- 因此這裡把封包只當成來源：
  - 新訓練 checkpoint 先複製快照到本 sandbox
  - 比較報告也複製到本 sandbox
  - 之後所有新 external recon 與 audit 輸出都只落在 `D:\GMM_2_Final`

## 目錄結構

- `artifacts/newpsf_r26_retrain/weights/`
  - 新 PSF 重訓後的 checkpoint 快照
- `artifacts/newpsf_r26_retrain/training_meta/`
  - `run_meta.json` 與 validation log 快照
- `external_compare/newpsf_r26_retrain/`
  - 這次外部 GMF 驗證的工作目錄
- `reports/`
  - 比較報告與 sandbox 狀態摘要
- `psf_audit/`
  - PSF 正式流程審核摘要
- `Tools/`
  - 這個 sandbox 的重跑腳本

## external compare 目前使用的權重

- `D:\GMM_2_Final\Experiments\R26NewPSFCheck\artifacts\newpsf_r26_retrain\weights\best_tradeoff.pth.tar`

來源是封包內這次新 PSF 重訓的最佳權重快照，而不是直接從封包路徑執行。

## external compare 目前輸出位置

- `D:\GMM_2_Final\Experiments\R26NewPSFCheck\external_compare\newpsf_r26_retrain`

這裡已完成三個資料集的 odd-frame reconstruction：

- `Pitch1um_Y_100`
- `Pitch0.1um_Y_60`
- `Pitch0.01um_Y_40`

## 給外部 GMF 的對接位置

外部 GMF 結果請回填到：

- `D:\GMM_2_Final\Experiments\R26NewPSFCheck\external_compare\newpsf_r26_retrain\gmf_results\raw\pitch8px\GMF_score.txt`
- `D:\GMM_2_Final\Experiments\R26NewPSFCheck\external_compare\newpsf_r26_retrain\gmf_results\raw\pitch0p8px\GMF_score.txt`
- `D:\GMM_2_Final\Experiments\R26NewPSFCheck\external_compare\newpsf_r26_retrain\gmf_results\raw\pitch0p08px\GMF_score.txt`

## 相關文件

- 新舊效果比較：
  `D:\GMM_2_Final\Experiments\R26NewPSFCheck\reports\new_psf_retrain_compare_20260326.md`
- PSF 正式流程審核：
  `D:\GMM_2_Final\Experiments\R26NewPSFCheck\psf_audit\PSF_FORMAL_AUDIT_20260326.md`
- sandbox 狀態摘要：
  `D:\GMM_2_Final\Experiments\R26NewPSFCheck\reports\STATUS_20260326.md`
