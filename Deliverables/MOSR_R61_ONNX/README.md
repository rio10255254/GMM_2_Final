# MOSR R61 ONNX

這個資料夾可直接用來重建顯微影像。模型採用已驗證的 R61 設定，適合均華、HS100MG 與相近的亮環或位移量測影像。

## 安裝

```powershell
python -m pip install -r requirements.txt
```

## 執行單張影像

```powershell
python run.py --input example\input.bmp --output output
```

## 執行整個資料夾

```powershell
python run.py --input input --output output
```

## 5120 × 5120 大圖

```powershell
python run.py --input input --output output --tile-size 640 --halo 192
```

新的分塊模式採用固定相位、反射 halo 與核心裁切。每一塊只保留中央核心，不再用重疊影像直接平均，因此不會把兩個稍有位移的邊界混在一起。`640 / 192` 已在真實 5120 × 5120 影像上完整執行通過。

若顯示記憶體足夠，可加入 `--tile-batch 2` 加速；已確認 batch 1 與 batch 2 輸出完全相同。程式會拒絕小於 192 或不是 64 倍數的 halo，以免錯誤設定破壞接縫。

預設不加 `--tile-size` 時仍採整張處理，並保留原 R61 驗證結果。R61 模型內含空間正規化與 FFT 光學處理，因此分塊輸出無法保證與整張輸出逐位元相同；三張真實 2180 × 1520 影像的實測最大灰階差為 11，95% 像素差異不超過 2，接縫區沒有額外放大誤差。

輸入可為 BMP、PNG、JPG 或 TIFF。彩色影像會先轉成灰階；目前只支援 8 位元影像。輸出統一為 BMP，尺寸與輸入相同。

這個版本是為已驗證的量測影像準備的應急交付版。遇到不同材料、極低對比或完全不同形狀時，應同時保留原圖確認。
