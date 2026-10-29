# V42 SoftLabel SNR Standalone Model Package

這是一個整理後的獨立模型包。正常使用時，它不需要再回頭讀取原本的大專案或小專案路徑。

## 這包裡有什麼

- `model_v42.py`：目前 V42 模型本體。
- `train_v42.py`：獨立訓練入口，預設只讀本資料夾內的訓練資料、PSF 與起始權重。
- `infer_v42.py`：獨立推論入口，預設使用本資料夾內的 V42 最佳權重。
- `utils_v42.py`：訓練與推論共用的小工具。
- `training_data`：本模型使用的完整 V42 訓練資料包，共 180 組影像與標籤。
- `weights`：本模型的權重集合，包含 V42 最佳權重、最新權重、epoch0 基準權重，以及 V42 微調時使用的 V41 起始權重。
- `psf`：本模型訓練時使用的 PSF 檔案。
- `results/training_results/final_smoke_run`：目前已完成的 V42 訓練測試結果。
- `results/inference_results`：推論輸出位置，目前已放入一次 sample 重建結果。
- `sample_inputs`：給推論程式快速驗證用的三張輸入影像。
- `docs`：保留這次 V42 設計與 smoke training 的補充紀錄。

## 直接推論

在這個資料夾中執行：

```powershell
python .\infer_v42.py --device cpu --output-name smoke_verify
```

若要使用 GPU：

```powershell
python .\infer_v42.py --device cuda:0 --output-name your_run_name
```

不指定其他參數時，它會自動使用：

- 輸入影像：`sample_inputs`
- 權重：`weights/best_tradeoff.pth.tar`
- 輸出：`results/inference_results`

## 直接訓練

先檢查包內資料是否完整：

```powershell
python .\train_v42.py --dry-run --device cpu
```

跑一次與目前 V42 smoke 設定相同的小訓練：

```powershell
python .\train_v42.py --device cuda:0
```

如果之後要做完整訓練，可以把 epoch 加大，並用全部 batch：

```powershell
python .\train_v42.py --device cuda:0 --num-epoch 120 --max-train-batches -1 --run-name full_training
```

## 目前這包已驗證

- `train_v42.py --dry-run --device cpu` 可正常讀到包內資料、PSF、起始權重與固定切分。
- `infer_v42.py --device cpu --output-name smoke_verify --print-model-config` 已成功重建三張 sample image。
- 推論時確認啟用了 V42 的 image-quality/SNR gate。

## 注意

這包目前收錄的是 V42 smoke model 的完整資料與結果。它可以作為乾淨、可搬移、可重跑的模型版本；但這次 V42 smoke training 本身仍是短訓練，不應在論文中直接說成完整長訓練後的最終性能。
