# R103：讓答案跟輸入共享曝光，拿掉會抹掉細節的正規化

[研究時間線](<../../docs/research/TIMELINE.md>) · [前一輪 R102](<../R102_UniversalDetailScratch/FILE_GUIDE.md>) · [下一輪 R104](<../R104_PhotometricInvariantCausalGateScratch/FILE_GUIDE.md>) · [R100～R104 完整結果的閱讀入口](<../../docs/reproducibility/project_completion/curated/FAILURE_LINEAGE_READING.md>)

**一句話：** R102 的稽核發現特徵正規化會抹掉細微的局部幅度與細節線索，而且有些資料要求模型猜一個只看輸入無法得知的曝光修正。R103 讓訓練觀測由程式真值經過可還原的局部光學前向模型產生，曝光、對比、gamma、照明同時套在輸入與答案上；每個退化裁切都配一個完全相同的清楚裁切；拿掉特徵正規化；低頻、輪廓、紋理三個目標不重疊；損失權重固定。2026-08-15 從零完成 48 輪。實拍六組位移都通過，而且逐步標準差六組都比 R61 低；但 SEM 跟原圖幾乎一樣，第 18 號曝光有明確的輪廓失敗。

| | |
|---|---|
| 結果 | **未採用**（曝光轉折處失敗） |
| 時間 | 2026-08-15（15:14 啟動，48 輪） |
| 實驗條件 | R92 固定合成資料經可還原前向模型產生；實拍 301 張、36 顆柱 SEM、200 張外部精確真值只用於後測 |
| 起點 | 隨機初始化，種子 1030053；2,189,605 個參數 |

## 結果

| 測試 | 結果 |
|---|---|
| 內部測試（第 48 輪） | PSNR 36.2 dB、輪廓 IoU 0.922、紋理恢復 0.281 |
| 實拍位移 | 六組全部通過，**逐步標準差六組都比 R61 低** |
| 36 顆柱 SEM：IoU 中位數 | 原圖 0.9490、R61 0.9584、R103 0.9492 |
| 36 顆柱 SEM：平均邊界距離 | 原圖 0.5697、R61 0.4413、R103 0.5716（% 柱距；18/36 顆改善） |

## 讀這些數字要知道的事

1. **第 48 輪是內部測試選出的**（PSNR、MAE、輪廓重疊、紋理恢復、成對觀測都最好）。
2. **第 18 號曝光的輪廓失敗**以原始的 `final_summary.json` 與逐曝光摘要為準；共用閱讀入口特別寫明沒有借用 R104 的圖冒充 R103 的失敗圖。
3. **照明問題和清楚輸入的不必要改動仍在**，不能把一般紋理改善當成 SEM 輪廓全面勝出。
4. 6,672 筆實拍位移讀值來自同一批 301 張，不是重新拍攝。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 完整後測表（52 檔，含最終總結、實拍序列、SEM 輪廓） | 本資料夾 [results/posttraining_validation/](<results/posttraining_validation>)，已在 GitHub |
| 模型、訓練、推論程式與設定 | 本資料夾 [model/](<model>)、[training/](<training>)、[inference/](<inference>)、[config/](<config>) |
| 第 48 輪模型的身分與位置 | 見 [R100～R104 閱讀入口](<../../docs/reproducibility/project_completion/curated/FAILURE_LINEAGE_READING.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

## 原始報告

| 文件 | 內容 |
|---|---|
| [最終總結](<results/posttraining_validation/final_summary.json>) | 選模理由、內部測試、實拍位移、SEM、曝光 18 的限制 |
| [精選結果閱讀紀錄](<reports/R103_SELECTED_RESULT_RECORDS_20261021.md>) | 2026-10-21 補的閱讀脈絡 |
| [README](<README.md>) | 改了什麼與使用方式 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R103_RecoverableDetailScratch.md>)。
