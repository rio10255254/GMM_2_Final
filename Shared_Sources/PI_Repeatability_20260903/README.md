# 三十步三十趟的原始位移拍攝資料

這是2026年9月3日實際拍攝的30趟位移資料。每趟包含起點與30步，共31張相機原始BMP；全套為930張照片及30份原始`positions.csv`，不是模型重建影像。

原始ZIP名為`20260902_100MF_uncertainty.zip`，名稱的日期與內部拍攝日不同。原始雲端檔案位於[Google Drive](https://drive.google.com/file/d/18wjpjSrhOT39XoBxDU5lHISxc-Wg8pVl/view)。檔案為2,027,201,313 bytes；SHA-256為`a1d5f4b7b2c96286141774360bd23f0fa5955e5ac2592b06a899ac2e6a976aa5`。

## 取得與恢復

GitHub共用資料版本：[shared-pi-20260903-v1](https://github.com/rio10255254/GMM_2_Final/releases/tag/shared-pi-20260903-v1)。下載該版本的原始ZIP與核對資料，不需要原電腦的D槽、H槽或Google Drive同步資料夾。

已登入GitHub CLI時，在專案根目錄執行：

```powershell
gh release download shared-pi-20260903-v1 --repo rio10255254/GMM_2_Final --pattern 20260902_100MF_uncertainty.zip --dir downloads
python Tools/restore_pi_acquisition.py --archive downloads/20260902_100MF_uncertainty.zip --plan Shared_Sources/PI_Repeatability_20260903/original_frozen_capture_plan.json --output YOUR_NEW_DATA_FOLDER
```

恢復工具只需要Python 3.11以上，不需要顯卡或影像處理套件。輸出資料夾必須尚不存在。工具直接複製ZIP中的原始檔，不調整亮度、不轉換影像，也不執行任何模型；全部960份檔案都必須符合歷史實驗留下的原檔SHA-256，並逐筆核對平台X/Y、時間、影格與曝光。

原始平台CSV包含`image`、`x`、`y`、`frame`、`exposure_us`、`scan_started_at`及`recorded_at`。位置單位沿用原實驗確認的µm。平台讀值是原實驗參考，並不因此取得獨立校正或完整準確度資格。

## 保存與使用紀錄

- [原件逐檔核對清單](ORIGINAL_ACQUISITION_MANIFEST.json)記錄930張照片與30份原始平台CSV。
- [當時凍結的拍攝清單](original_frozen_capture_plan.json)保留舊路徑與原檔身分；舊下載位置目前已失效，不能把路徑文字當成檔案仍存在。
- [可改位置使用的拍攝清單](portable_capture_plan.json)使用資料夾內的相對位置。
- [引用實驗清單](referencing_experiments.json)區分來源引用與完成實拍驗證，不能把兩者混為一談。

2026年10月16日從原始Google Drive ZIP取回，全部960份原檔與歷史清單一致。先前曾從R139失敗模型的固定亮度偏移輸出恢復930張副本；這些副本亦與原始ZIP逐檔一致，但正式共用來源採用本次直接從原始ZIP取出的檔案。

原始ZIP與逐檔核對清單必須共同保存。`raw/`是本機解開後的工作副本，不重複放進一般Git歷史；完整原始ZIP隨GitHub版本附件保存。

2026年10月16日已從GitHub下載照片ZIP、拍攝清單與恢復程式，在無法讀取舊D/H資料的另一位置完整還原960份原件。全部通過，見[取回重做核對](GITHUB_ROUNDTRIP_VERIFIED.json)。
