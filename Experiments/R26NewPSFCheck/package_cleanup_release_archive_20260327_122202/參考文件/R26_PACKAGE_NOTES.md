# GeoEdge R26 封包說明

這份封包已改成拆分交付。

## 1. 交付方式

- `主包`
  - 給大多數使用者直接跑
  - 保留入口、模型、權重、訓練資料與示範資料
- `GPU 補丁`
  - 只在需要獨立 GPU runtime 時另外傳送
  - 離線安裝，不需要網路

## 2. 為什麼要拆

原本最大的體積來源是 portable GPU runtime。  
它對某些機器有用，但不是每台機器都需要。

因此現在改成：

1. 先把主包壓小
2. 平常能用本機 Python / CUDA 就先用本機
3. 本機不適合時，再安裝 GPU 補丁

## 3. 本次拆分的體積概況

以目前這版拆分結果來看：

- 主包：約 `0.86 GB`
- GPU 補丁：約 `5.5 GB`

換句話說，平常只傳主包時，使用者不需要先收到那個最大塊的 GPU runtime。

## 4. 主包保留了什麼

- `內部檔案\weights\r26_sm035_best_tradeoff.pth.tar`
- `內部檔案\Training_Data\`
- `內部檔案\Demo_Input\`
- `Model/`、`PSF_Fitting/`、啟動器腳本與輸出資料夾

補充：

- 主包不再預附 `.venv`
- 如果本機 Python 可用，第一次執行時會在封包內建立該台機器自己的 `.venv`

## 5. GPU 補丁保留了什麼

- `portable_runtime`
- 安裝 / 回退腳本
- 補丁描述檔

## 6. 什麼情況要裝 GPU 補丁

只有在下列情況才建議裝：

- 主機有 NVIDIA GPU，但 Python / CUDA 環境不完整
- 你想把這套程式搬到另一台機器，並保留一套獨立 GPU runtime
- 你不想依賴目標機器原本安裝的 Python 套件

## 7. 什麼情況可以先不裝

如果你只是要：

- 先做 demo 推論
- 先跑 CPU 版本確認流程
- 先看訓練/推論輸出

那主包就夠了。

## 8. 目前保留的流程

- 推論：`RUN_DEMO_INFERENCE.bat`、`RUN_CUSTOM_INFERENCE.bat`
- 訓練：`RUN_QUICK_TRAIN.bat`、`RUN_FULL_TRAIN.bat`
- 初始化：`FIRST_RUN_SETUP.bat`
- 主入口：`START_HERE.bat`

## 9. 背景補充

- 正式 checkpoint 仍是 `r26_sm035_best_tradeoff.pth.tar`
- 本包目前預設是先用可用的本機環境
- 若本機環境不合適，啟動器會先提示缺件，再考慮補丁或 CPU 路線
