# 完整影像重建入口

此附加入口使用已訓練完成的R129第8192次權重。原始套件程式、起始模型及舊清單保持不變。它處理完整原生影像，光學與品質統計使用全圖，只有局部重建計算分段，解決直接放大完整2048×1536影像時的運算索引限制。

在套件資料夾使用：

```powershell
python addons/full_field/infer_fullfield.py --input-dir "D:\your_images" --output-name full_trial_01
```

需相同Python/CUDA環境；輸入8-bit灰階、至少193×193。输出存於results/inference/full_trial_01，保留原寬高；名稱不可重複。可用--checkpoint指定另一份相容R129權重；本次驗證的是第8192次，其他權重的效能不由此保證。

這是新的推論入口，不是重新訓練或正式採用模型。完整連續LSC分析與所有影像保存在Experiments/R129_OpticalPriorHybrid/results/continuous_lsc，對應報告另行產出。初版完整圖失敗與分段等價檢查均保留。
