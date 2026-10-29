# R124 — 可執行的下一代模型原型

本輪已實作完整二維、四步共享重建的原型，以及分塊推論、逐步紀錄與初始化檔案保存／重載。**這是未訓練的研究原型，不是已改善實拍量測的模型。**

沿用 R123 的設計方向，實際範圍見 [原型結果與限制](reports/R124_RESULTS.md)。這裡的兩個成像設定只作工程測試，均未經儀器校準；SEM 不會輸入模型。所有舊資料與證據只讀。

## 實際使用

在 PowerShell 中執行，輸出資料夾必須尚不存在：

```powershell
& 'C:\Users\Rio\anaconda3\python.exe' 'Experiments/R124_RealFirstPrototype/inference/run.py' `
  --input 'Experiments/R119_SequenceGeometryValidation/validation/inputs/Raw/20x_mixed_raw.bmp' `
  --output 'Experiments/R124_RealFirstPrototype/results/my_diagnostic' `
  --profile 'Experiments/R124_RealFirstPrototype/config/gaussian_diagnostic.json' `
  --device cuda
```

輸出包含：浮點影像 `.npz`、顯示用 `.png`、`initialization.pth`、以及記錄來源和「未訓練／未校準」身分的 `inference.json`。資料夾輸入也可以；目前命令列接受原始灰階8位元影像，不會默默用每張圖的最大最小值重新正規化。

重新載入同一初始化：把 `--profile` 換成 `--checkpoint '<已保存的initialization.pth>'`，並指定另一個新輸出資料夾。初始化檔案已綁定成像設定，不接受另傳設定覆蓋。實際重載測試的浮點影像完全一致。

## Python API

```python
from model.calibration import load_observation
from model.network import build_model
from inference.tiling import tiled_forward

observation = load_observation('config/gaussian_diagnostic.json', device='cuda')
model = build_model({'checkpoint_blocks': True}, observation).cuda().eval()
# raw: float32 N x 1 x H x W, camera units divided by255
output = tiled_forward(model, raw, core=256)
details = model.forward_details(raw, trace=True)
```

`details` 提供原大小輸出、2倍內部格點、一般幾何診斷、四步完整紀錄，以及尚未校準的身分。幾何只是未學習的輔助輸出，其數字不是實際量到的答案或可靠信賴區間。

## 驗證指令

在本資料夾執行：

```powershell
& 'C:\Users\Rio\anaconda3\python.exe' -m unittest discover -s tests -v
```

完整大小與真實輸入的可重跑程式：

- `scripts/run_runtime_checks.py --mode backward --output <新資料夾>`：兩張640px真實輸入的反向運算，沒有參數更新。
- `scripts/run_runtime_checks.py --mode tiles --output <新資料夾>`：非零修正下的整圖／分塊及最大光學核支援檢查。
- `scripts/run_real_smoke.py --output <新資料夾> --device cuda`：六張固定實拍圖、兩個未校準成像假設、四步紀錄。
- `scripts/measure_sem_smoke.py`：SEM參考半對比讀值接線，參數與範圍見程式說明；它不是完整SEM驗收。

## 邊界與保留

Profile中的`physical_psf`只在讀取時翻轉一次，以對接PyTorch相關運算；不重設中心、不自動改校準數值。觀測算子採有限域零延伸，這是數值邊界假設，不是宣稱感測器外一定為黑色。分塊使用足夠周邊後丟棄人工分界；原圖最外邊界的物理有效性仍未認證。

自包含型態，分支 `codex/r124-real-first-prototype`。容量預算2GiB；保留所有程式、測試、失敗紀錄、原型輸出和來源指紋。沒有正式訓練集、沒有優化器更新、沒有新確認結果；不移動或删除歷史資料。
