# 自適應選擇機制的受控測試

這些測試在暫存目錄建立**人造且相互可分的 PSF**，不會寫入可執行模型的 `calibration/`。測試意義是證明程式可學，不是證明現有實測 25 顆或尚未安裝的 100 顆有足夠物理差異。

`probe_selector.py` 實測 25→4 及 100→8：前向分別只有 4、8 個非零權重；未入選候選分數仍得到非零梯度，選擇網路首尾層都有梯度。以已知特徵的控制例訓練後，兩種設定的分數首選與前 K 覆蓋率均為 100%。

`probe_physical_selection.py` 把同樣來源的線段與圓點用四種可分辨的高斯模糊產生影像，訓練影像特徵選擇器，另用 16 個未見場景共 64 張影像驗證。25→4：首選 64/64、前四包含真候選 64/64；100→8：首選 64/64、前八包含真候選 64/64。這比人工把類別直接寫進輸入更接近預期的模糊辨識，但仍是受控合成測試。

`integration_full_model.py` 在完整四次修正 U-Net 中使用 R140v2 非光學主網路及暫時產生的不同 PSF，兩個規格都完成前向與反向、恰選 K 顆，未入選分數仍有非零梯度。梯度幅度很小，因此實際自適應長訓練仍需要有辨識力的銀行與配對標記；這個測試不是實拍成效的保證。

`probe_external_labeled_data.py` 另以暫存標記檔讀入兩張配對影像的 `psf_index=[0,8]`，確認訓練讀取器可接收外部已標記資料，而包內原始中繼資料不變。外部資料根目錄的四次更新煙霧測試也已通過。

重跑：

```powershell
& 'C:\Users\Rio\anaconda3\python.exe' tests/probe_selector.py
& 'C:\Users\Rio\anaconda3\python.exe' tests/probe_physical_selection.py
& 'C:\Users\Rio\anaconda3\python.exe' tests/integration_full_model.py
& 'C:\Users\Rio\anaconda3\python.exe' tests/probe_external_labeled_data.py
```

整體網路的實拍煙霧測試與每包狀態另見其 `README.md`、`verify_package.py` 及 `results/`。現有 25 顆 PSF 的成對相似度過高，因而不把本測試的成功轉寫成實拍 PSF 自適應已獲證實。
