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

程式預設整張處理，避免大圖出現分區接縫。若電腦記憶體不足，可在指令後加入 `--tile-size 1024 --overlap 128`。

輸入可為 BMP、PNG、JPG 或 TIFF。彩色影像會先轉成灰階；目前只支援 8 位元影像。輸出統一為 BMP，尺寸與輸入相同。

這個版本是為已驗證的量測影像準備的應急交付版。遇到不同材料、極低對比或完全不同形狀時，應同時保留原圖確認。
