# R70：V42E120 的 SEM 完整輪廓驗證

這個實驗把論文採用的 V42 epoch 120 重新套用到與 R69 完全相同的曝光 13–24 影像，並使用相同 36 顆 SEM 真值、相同輪廓擷取參數及只平移的對齊方式。

主要目的不是再量一次圓半徑，而是回答：V42 重建後的完整外形是否更接近逐顆對應的 SEM，以及它在極暗曝光下是否仍穩定。

執行完整流程：

```powershell
& 'C:\Users\Rio\anaconda3\python.exe' 'D:\GMM_2_Final\Experiments\R70_V42ACMContourSEMValidation\scripts\run_r70.py' --stage all
```

結果資料夾包含：

- `results/figures`：重建前後、逐顆輪廓及模型比較圖。
- `results/tables`：每顆、每張曝光與配對統計結果。
- `reports/R70_RESULTS_TW.md`：可直接閱讀的中文結論。
