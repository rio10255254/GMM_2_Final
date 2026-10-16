# R82 R39 / R40 跨場景泛化與位移驗證

本輪把 R39、R40、兩者的平衡版，和 Raw、正式 COMBO、R61、R79 放在相同輸入與相同規則下比較。

固定驗證範圍：

- 301 張 5× / 20× / 50× 真實顯微位移影像。
- 均華三種位移尺度的固定 100 / 60 / 40 張序列。
- 100 張新形狀與 100 張高難度顯微合成影像，使用相同 ACM 輪廓規則。
- 12 張光學曝光影像對應 36 顆真實 SEM pillar。
- 舊有外部 GMF 數字只放在有實測的 COMBO、R39、R40、R39R40，缺測模型不補值、不混合平均。

一鍵執行：

```powershell
C:\Users\Rio\anaconda3\python.exe scripts\run_r82.py --stage all
```

結果會集中在 `results`，最後結論在 `reports/R82_RESULTS_TW.md`。本輪不會修改正式基準或任何既有模型權重。
