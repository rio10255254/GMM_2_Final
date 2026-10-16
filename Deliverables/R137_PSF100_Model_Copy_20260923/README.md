# R137 模型副本 可接收100顆PSF

只改PSF接收數量；已訓練的神經參數及0.02強度不變，原R137不動，沒有重新訓練。

模型檔：weights/R137_original_trained.pth。
之後將100顆PSF放入calibration/psf_100.npz，陣列all_kernels形狀為(100,101,101)。

載入：
```python
from model_api import load_model
model, info = load_model(device='cuda')
```

入口會用新100顆的平均PSF取代模型內的舊平均值，其餘權重不改。尚未放入資料時會提示缺檔，不沿用舊25顆。
