# MOSR ONNX

這是 R79 的可直接執行版本。模型、光學資料及執行程式必須放在同一個資料夾。

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

預設安裝使用 CPU。若環境已另外安裝可用的 NVIDIA 版本，程式會自動使用；要固定使用 CPU，可在指令最後加上 `--cpu`。

輸入可為 BMP、PNG、JPG 或 TIFF。彩色影像會先轉成灰階；目前只支援 8 位元影像。輸出統一為 BMP，尺寸與輸入相同。

每張影像只會以完整影像重建一次，不會切成小塊。請不要自行先切圖再拼接，否則結果會改變。

已驗證的輸入範圍：寬與高至少 21 像素、都不超過 2180 像素，而且總像素不超過 3,313,600。這包含目前的 1520×2180 與 1536×2048 真實影像。超出範圍時程式會直接停止，不會偷偷改用另一種處理方式。

模型適合與驗證資料相近的顯微成像。遇到極低對比、嚴重光暈或邊界消失時，請同時保留原圖確認，不應只依賴重建結果。
