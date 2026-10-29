# R71 — R61 合成顯微缺陷泛化測試

這一輪使用既有 R40 實驗中保留、沒有參與 R61 訓練的 100 張合成顯微影像，檢查 R61 是否能讓格網、區域邊界、紋理、邊緣缺損與混合缺陷更接近已知的乾淨答案。

主要比較是 Raw 對 R61；同一測試集既有的 COMBO 重建只作為舊基準參考。邊緣缺損與混合缺陷共 40 張，另列為缺陷核心組。

完整執行：

```powershell
& 'C:\Users\Rio\anaconda3\python.exe' 'Experiments/R71_R61SyntheticMicroscopyDefectGeneralization/scripts/run_r71.py' --stage all
```

結果說明在 `reports/R71_RESULTS_TW.md`。
