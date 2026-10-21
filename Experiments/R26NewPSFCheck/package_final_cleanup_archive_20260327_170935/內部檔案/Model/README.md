# Model / 正式 R26 模型說明

這份 package 內的 `Model/` 目的是支援兩件事：

1. 使用目前標準 `r26_sm035` 權重做推論
2. 在 package 內以歷史 `R26 / r26_sm035` baseline 做完整重新訓練

## 1. 這裡有哪些核心檔案

- `GeoEdgeAlignSR_v1_ModelA_v5_NoCoord.py`
  - 模型定義
- `GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py`
  - 底層訓練腳本
- `GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py`
  - 底層推論腳本
- `GeoEdgeAlignSR_v1_Utils.py`
  - 共用工具函式
- `GeoEdge_R26_FormalTrainAdapter.py`
  - package 內正式 `R26` recipe 的 Python adapter

## 2. 這裡的腳本和正式 R26 的關係

這些底層 train / infer 腳本本身是通用執行入口。  
正式 `R26` 的歷史效果 **不是只靠腳本檔名** 決定，而是靠：

- current-standard 新 PSF
- 正式 `r25_sw010` seed checkpoint
- current-standard `r26_sm035` replacement checkpoint
- 正式 stage subset dataset
- 固定 seed / deterministic
- 固定 historical overrides

這些內容都由：

- `..\formal_r26_recipe.json`
- `..\GeoEdge_R26_FormalTrain.ps1`
- `..\GeoEdge_R26_FormalInfer.ps1`

來固定套用。

換句話說：

- 底層腳本 = 可執行引擎
- formal wrapper + recipe = 正式 `R26` baseline 語意

## 3. 使用 baseline 重新訓練時不要直接做什麼

如果你的目的是使用目前標準 `R26 / r26_sm035` baseline 重新訓練，不要直接：

- 手動修改 train script 預設值
- 自己混用非正式 checkpoint / PSF 路徑
- 把 `RUN_QUICK_TRAIN` 結果當正式 R26
- 省略 `r25_sw010` seed checkpoint

完整重新訓練應該走：

- `RUN_FULL_TRAIN.bat`

這會透過 formal wrapper 自動載入固定 recipe。

## 4. 推論模式

### 正式推論

走：

- `RUN_DEMO_INFERENCE.bat`
- `RUN_CUSTOM_INFERENCE.bat`

這兩條線固定使用：

- `..\weights\r26_sm035_best_tradeoff.pth.tar`
- checkpoint 內封存的 current-standard PSF buffer

### 為什麼預設用 checkpoint 內 PSF

因為這份 package 要重現目前採用的標準效果。  
若讓舊 checkpoint 在推論時跟著外部 `.mat` 自動漂移，歷史可重現性就會被破壞。

所以 package 預設規則是：

- current-standard checkpoint 推論：使用 checkpoint 內 PSF
- 完整重新訓練：使用 package 內 current-standard PSF

## 5. 訓練模式

### Quick smoke

- 入口：`RUN_QUICK_TRAIN.bat`
- 用途：流程 smoke test
- 輸出：`..\輸出結果\訓練結果\_smoketest\`

### 完整重新訓練

- 入口：`RUN_FULL_TRAIN.bat`
- adapter：`GeoEdge_R26_FormalTrainAdapter.py`
- recipe：`..\formal_r26_recipe.json`

這條線固定鎖定歷史 `R26 / r26_sm035` baseline：

- `winner_name = r26_sm035`
- `source_winner_kind = sweep`
- `kind = full_train_baseline`
- `model_name = GESR_v1_v5_ST0p8_SWP_r26sm035`

不切去 generic candidate sweep；它會沿用歷史 baseline 配置做完整重新訓練。

## 6. 路徑假設

這份 package 的底層腳本都假設自己位於：

```text
GeoEdge_R26_使用包/
└── 內部檔案/
    ├── Model/
    ├── Training_Data/
    ├── PSF_Fitting/
    ├── weights/
    └── formal_r26_recipe.json
```

因此若要保持 package 可用，請不要任意改動這些相對位置。
