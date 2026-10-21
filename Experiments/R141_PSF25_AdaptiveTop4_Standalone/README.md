# 25 顆 PSF 自適應選四顆獨立包

這包已內含真實 25 顆 PSF、合成訓練資料副本、模型程式、訓練與推論入口、衍生權重、來源檢查及測試。推論現在即可執行。衍生權重沿用已驗證 R140v2 的非光學主網路，光學選擇器是新初始化，**尚未證明會在現有 25 顆幾乎相同的 PSF 之間作有意義的自適應選擇**；它不能冒充重新長訓練的新結果。

先用 `C:\Users\Rio\anaconda3\python.exe verify_package.py --mode infer-ready` 核對。重建單張影像使用：

```powershell
& 'C:\Users\Rio\anaconda3\python.exe' infer.py --input 'D:\your_image.bmp' --output 'D:\your_result.npz' --device cuda
```

同名 `.png` 是顯示圖，`.npz` 保留原始 FP32 數值；`.json` 記錄四顆入選索引、權重、模型與 PSF 來源。如果沒有 GPU，可改 `--device cpu`，但完整尺寸會較慢。輸出檔已存在時會拒絕覆蓋。

若要從零長訓練自適應選擇，需要每張訓練影像的合適 PSF 真值，於資料側的 JSON 加入 `psf_index`（兩張配對影像可用同一整數或兩個整數）。請把新資料放在另一個資料夾，保持原來的 512/128/128 母場景清單格式，使用 `--data-root 'D:\new_labeled_data'`；包內原資料不用修改。現有資料沒有這個欄位；預設訓練會拒絕將無標記資料誤當成自適應訓練。探索性非自適應訓練才使用：

```powershell
& 'C:\Users\Rio\anaconda3\python.exe' train.py --run-name exploratory_unlabeled --init derived --allow-unlabeled-psf
```

`--init scratch` 可從零開始；`--smoke` 僅作四次更新檢查，不產生可用新模型。正式訓練輸出另放在 `runs/<run-name>`，舊 R140v2 的模型、930 張結果及校驗一律不改動。

模型設計與自適應機制測試詳見 `MODEL_CARD.md` 和 `tests/`。目前衍生版在一張固定實拍上與 R140v2 輸出的 RMS 差約 `1.40 × 10⁻⁶` 個八位元灰階；這是相容性煙霧測試，不代表已完成全 930 張新模型驗證。
