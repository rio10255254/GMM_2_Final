# V42 SoftLabel SNR Full Standalone Model Package

這是一個正式 full training 用的獨立模型包。它的設計目標是簡潔、明確、完整：模型、訓練、推論、資料、PSF、權重與結果都集中在同一個資料夾內。

## 這包的定位

這包不是只有 180 組 smoke data 的小測試包。

它的 `training_data` 是完整訓練資料：

- 11,254 組影像與標籤
- 15 類資料
- 由 V41 full training dataset 作為主體
- 另外將 V42 的 180 組 soft-label 邊界標籤疊加進去

也就是說，這包可以用來做正式 V42 full retraining。

## 主要檔案

- `model_v42.py`：V42 模型本體。
- `train_v42.py`：正式訓練入口，預設只讀本資料夾內的資料、PSF 與權重。
- `infer_v42.py`：推論入口，預設使用本資料夾內的 V42 smoke 權重；完整長訓練完成後可改指定新權重。
- `utils_v42.py`：訓練與推論共用工具。

## 主要資料夾

- `training_data`：正式 full training 使用的 active dataset。
- `weights`：目前可用權重，包含 V41 起始權重與 V42 smoke 權重。
- `psf`：本模型使用的 PSF 檔案。
- `results/training_results`：訓練輸出位置，目前含一份 V42 smoke 參考結果。
- `results/inference_results`：推論輸出位置，目前含三張 sample 重建結果。
- `sample_inputs`：快速測試推論用的三張影像。
- `docs`：資料疊加報告、原始 manifest、V42 smoke 紀錄等補充資料。

## 檢查資料完整性

```powershell
python .\train_v42.py --dry-run --device cpu
```

這個命令只檢查路徑與設定，不會開始訓練。

## 正式完整訓練

```powershell
python .\train_v42.py --device cuda:0
```

預設設定：

- 120 epochs
- 使用全部 training batches
- 從包內 V41 起始權重接續訓練
- 啟用 V42 的 image-quality/SNR gate
- 訓練輸出放在 `results/training_results`
- 每個 epoch 都保存一次權重

如果要從零開始：

```powershell
python .\train_v42.py --device cuda:0 --scratch --run-name full_training_scratch
```

## 正式訓練加每 epoch 三倍率展示

若要同時啟動完整訓練與每個 epoch 的 100MG 三倍率展示推論，執行：

```powershell
.\start_full_training_with_epoch_demos.ps1
```

這個啟動器會：

- 用 GPU 跑完整訓練。
- 用 CPU 跑每個 epoch 的示範推論，避免跟訓練搶 GPU 記憶體。
- 每個 epoch 使用 `demo_inputs` 裡的 100MG 50x、20x、5x sample。
- 將展示推論放在該次訓練資料夾的 `epoch_demo_inference` 裡。
- 將啟動紀錄、PID 與 stdout/stderr log 放在 `results/run_logs` 裡。

## 推論

先跑 sample input：

```powershell
python .\infer_v42.py --device cpu --output-name smoke_verify
```

完整訓練完成後，若要指定新權重：

```powershell
python .\infer_v42.py --device cuda:0 --weights .\results\training_results\你的訓練資料夾\weights\best_tradeoff.pth.tar --input-dir 你的影像資料夾 --output-name your_inference
```

## 目前已完成的驗證

- full training dataset 已建立：11,254 組資料。
- V42 soft-label overlay 已疊加：180 組標籤。
- `train_v42.py --dry-run --device cpu` 可正常讀到包內資料、固定切分、PSF 與起始權重。
- `infer_v42.py --device cpu --output-name smoke_verify --print-model-config` 已成功重建三張 sample image。
- 推論時確認 V42 的 image-quality/SNR gate 有被載入。
- 核心程式沒有硬編碼連回原本大專案路徑。
- `epoch_demo_monitor.py` 已通過測試，也已用目前 V42 權重預演過三倍率展示推論。

## 重要提醒

目前這包已經可以啟動正式完整重訓，但完整 120 epoch 長訓練尚未在這包內跑完。現在 `results/training_results/v42_smoke_reference_run` 是參考用的短訓練結果，不要把它寫成 full training 結果。
