# R142：100 顆 PSF 每張挑 8 顆（等實測 PSF 安裝的空包）

[研究時間線](<../../docs/research/TIMELINE.md>) · [25 顆版本 R141](<../R141_PSF25_AdaptiveTop4_Standalone/FILE_GUIDE.md>) · [下一輪 R143](<../R143_PSF25_MatchedPairs/FILE_GUIDE.md>)

**一句話：** 跟 R141 同一套架構，只是候選擴到 100 顆、每張挑 8 顆。2026-09-23 把包做好、機制測試也通過，但包裡**沒有安裝 100 顆實測 PSF**，所以推論會明確拒絕執行，這是設計上的正確行為。測試用的合成 PSF 只出現在測試程序的暫存目錄，不會被當成實測校準。

| | |
|---|---|
| 結果 | **中止**（指定的實測 100 顆 PSF 尚未安裝，沒有可用模型） |
| 時間 | 2026-09-23 |
| 實驗條件 | 包內帶 512／128／128 合成母場景副本；受控測試用人造 PSF |
| 起點 | 主網路沿用 R140v2 的非光學權重（未訓練的起點） |

## 讀這些內容要知道的事

1. **受控測試結果跟 R141 一樣**：100 選 8 的首選與前八覆蓋都是 64/64；在隔離副本裡用測試銀行跑原尺寸前向約 1.6 秒、GPU 峰值約 4.2 GiB，只說明容量，不代表品質。
2. **`PSF_Fitting` 裡有一份 2026 年 3 月的 full100 舊候選**，差異比早期版本明顯，但它跟目前影像的尺度、樣本與 SEM 真值關係還沒對接，所以沒有被偷偷拿來用。
3. **要讓它可用**，需要：把 100 顆實測 PSF 存成 `(100,101,101)` 的 NPZ 並附來源 JSON，用 `install_bank.py` 安裝；再準備帶逐張 `psf_index` 的配對資料訓練，最後做實拍與 SEM 驗證。

## 拿資料與重做

`verify_package.py --mode structural` 可在沒有 PSF 的情況下檢查結構；安裝與訓練步驟見 [README](<README.md>)，等待安裝的說明見 [calibration/BANK_REQUIRED.md](<calibration/BANK_REQUIRED.md>)。

## 原始報告

[封裝驗證](<results/PACKAGE_VALIDATION.md>)、[技術卡](<MODEL_CARD.md>)、[受控測試](<tests/VALIDATION.md>)、[包裝修訂紀錄](<PACKAGING_CHANGELOG.md>)。2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R142_PSF100_AdaptiveTop8_Standalone.md>)。
