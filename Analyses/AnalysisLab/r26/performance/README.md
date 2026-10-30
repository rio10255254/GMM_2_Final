# R26 效能基準測試（Performance Benchmark）

## 這是什麼

量化 R26 模型在不同設備上的**推論效能**和**訓練效能**。

設計目標：帶到任何一台新機器上，**只改一個設定檔**就能跑。結果自動按設備名歸檔，最後可以匯總做跨設備比較。

## 目錄結構

```
performance/
├── README.md                          ← 你正在看的這個檔案
├── scripts/
│   ├── run_inference_benchmark.py     # 推論效能基準測試
│   ├── run_training_benchmark.py      # 訓練效能基準測試
│   └── run_cross_device_compare.py    # 跨設備匯總比較（不需要 GPU）
├── tests/
│   └── test_performance_benchmark.py  # pytest 結構驗證
├── configs/
│   └── device_config.py              # ★ 唯一需要改的檔案 ★
├── results/
│   ├── <DEVICE_NAME>/               # 每台設備一個子目錄
│   │   ├── inference_benchmark.json # 推論 benchmark 的機器可讀結果
│   │   ├── inference_summary.md     # 推論 benchmark 的人類可讀摘要
│   │   ├── training_benchmark.json  # 訓練 benchmark 的機器可讀結果（若有跑）
│   │   └── training_summary.md      # 訓練 benchmark 的人類可讀摘要（若有跑）
│   └── cross_device/                 # 匯總比較結果
│       ├── device_comparison.json
│       └── *.png
└── reports/
    └── R26_Performance_Report.md
```

---

## 快速開始（本機）

如果你只是想在目前的機器上跑一次，三步就好：

```bash
# 1. 確認 device_config.py 裡的路徑正確（預設值是本機路徑，可能不需要改）
# 2. 跑推論 benchmark
python Analyses/AnalysisLab/r26/performance/scripts/run_inference_benchmark.py

# 3. 跑訓練 benchmark
python Analyses/AnalysisLab/r26/performance/scripts/run_training_benchmark.py
```

結果會自動存到 `results/<DEVICE_NAME>/`，其中 JSON 給腳本/CI 用，Markdown summary 給人直接讀。

---

## 在不同設備上測試：完整教學

### 前置準備：打包模型資產

在**本機**先把大檔案集中到一個資料夾（隨身碟、雲端資料夾皆可）：

```
geoedge_assets/                        ← 資料夾名稱隨意
├── best_tradeoff.pth.tar              ← 必要（~50MB）
├── PSF_fitted_2D_FOVstack.mat         ← 必要（幾MB）
├── tra_src_ring/                      ← 選配（333MB，跑訓練 benchmark 才需要）
│   ├── 6001.bmp
│   └── ...
└── tra_lbl_ring/                      ← 選配（333MB，跑訓練 benchmark 才需要）
    ├── 6001.bmp
    └── ...
```

本機的檔案來源：

| 檔案 | 本機路徑 |
|------|---------|
| `best_tradeoff.pth.tar` | `Experiments/Legacy/organized_20260316/round26/archive/runs/.../weights/` |
| `PSF_fitted_2D_FOVstack.mat` | `PSF_Fitting/Crop_circle_FreqFiltered/Fits/` |
| `tra_src_ring/` | `Training_Data/tra_src_ring/` |
| `tra_lbl_ring/` | `Training_Data/tra_lbl_ring/` |

> 不帶訓練集也能跑。推論 benchmark 只需要 checkpoint + PSF。
> 訓練 benchmark 沒有真實資料時會自動用合成資料（能量 GPU 速度但不含 I/O 開銷）。

### 第一步：取得程式碼 + 安裝環境

**方法 A：只 clone 需要的資料夾（推薦，~12MB）**

跑 benchmark 只需要 `Model/`、`Analyses/AnalysisLab/r26/performance/`、`Analyses/AnalysisLab/r26/single_image/inputs/` 三個資料夾，不需要整個專案（~260MB）。用 Git sparse checkout 可以只下載這些：

```bash
git clone --filter=blob:none --sparse https://github.com/rio10255254/GMM_2_Final.git
cd GMM_2_Final
git sparse-checkout set Model Analyses/AnalysisLab/r26/performance Analyses/AnalysisLab/r26/single_image/inputs
```

這樣 clone 下來的工作目錄只有 ~12MB。

**方法 B：完整 clone（如果你也需要看其他分析或實驗）**

```bash
git clone https://github.com/rio10255254/GMM_2_Final.git
cd GMM_2_Final
```

**安裝 Python 依賴：**

```bash
# 安裝 PyTorch（根據設備的 CUDA 版本選擇）
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121  # CUDA 12.1
# 或 pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118  # CUDA 11.8
# 或 pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu    # CPU only

# 其他依賴
pip install numpy scipy matplotlib opencv-python
```

### 第二步：執行 setup_device.py（互動式設定）

```bash
python Analyses/AnalysisLab/r26/performance/scripts/setup_device.py
```

它會問你兩件事：
1. **模型資產在哪？** → 輸入隨身碟/雲端資料夾的路徑（如 `E:\geoedge_assets` 或 `/mnt/usb/geoedge_assets`）
2. **設備名稱？** → 會自動偵測 GPU 型號並建議名稱，直接 Enter 或自己取

腳本會自動：
- 檢查必要檔案是否存在
- 偵測 GPU 資訊
- 若 benchmark package 旁邊已經有 `best_tradeoff.pth.tar` / `PSF_fitted_2D_FOVstack.mat` / 訓練資料，會直接採用
- 否則再詢問你模型資產所在路徑
- 產生正確的 `configs/device_config.py`
- 告訴你下一步要跑什麼

> 如果你偏好手動設定，也可以直接編輯 `configs/device_config.py`，欄位說明見檔案內的註解。

### 第三步：執行 Benchmark

```bash
cd GMM_2_Final

# 推論 benchmark（通常 1-2 分鐘）
python Analyses/AnalysisLab/r26/performance/scripts/run_inference_benchmark.py

# 訓練 benchmark（quick mode 通常 5-10 分鐘）
python Analyses/AnalysisLab/r26/performance/scripts/run_training_benchmark.py
```

如果只想測 GPU 不測 CPU（CPU 很慢）：

```bash
python Analyses/AnalysisLab/r26/performance/scripts/run_inference_benchmark.py --no-cpu
python Analyses/AnalysisLab/r26/performance/scripts/run_training_benchmark.py --no-cpu
```

如果要指定特定設備：

```bash
# 只跑 CPU
python Analyses/AnalysisLab/r26/performance/scripts/run_inference_benchmark.py --device cpu

# 跑第二張 GPU
python Analyses/AnalysisLab/r26/performance/scripts/run_inference_benchmark.py --device cuda:1
```

### 第四步：把結果送回來

結果存在 `results/<DEVICE_NAME>/` 裡，通常包含：

- `inference_benchmark.json`
- `inference_summary.md`
- `training_benchmark.json`（只有真的跑了 training benchmark 才會有）
- `training_summary.md`（只有真的跑了 training benchmark 才會有）

另外要注意：

- 如果你用 `--device cuda:0` 或 `--device cpu`，結果只會包含你指定的裝置
- 如果你用 `--no-cpu`，則該次結果不會包含 CPU baseline
- 因此 `results/<DEVICE_NAME>/` 不保證永遠同時含 GPU 與 CPU、也不保證 inference/training 一定都存在

**方法 A：Git commit + push（推薦）**

```bash
git add Analyses/AnalysisLab/r26/performance/results/
git commit -m "perf: add benchmark results for RTX_4090_Lab_B"
git push
```

**方法 B：手動複製**

把 `results/<DEVICE_NAME>/` 整個資料夾複製回本機的對應位置。
建議連同 `.json` 和 `.md` 一起帶回來，避免只剩機器可讀結果、沒有摘要。

### 第五步：跨設備比較

回到本機（或任何一台有所有結果的機器），拉最新的結果後：

```bash
git pull  # 如果用 git

# 跑跨設備比較（不需要 GPU，純讀 JSON 產圖表）
python Analyses/AnalysisLab/r26/performance/scripts/run_cross_device_compare.py
```

結果在 `results/cross_device/`：
- `device_comparison.json`：完整比較數據
- `01_inference_latency_comparison.png`：推論延遲對比
- `02_inference_throughput_comparison.png`：推論吞吐量對比
- `03_training_throughput_comparison.png`：訓練吞吐量對比（至少有一台設備提供 training JSON 才會產生）
- `04_gpu_memory_comparison.png`：GPU 記憶體對比

---

## 量測指標說明

### 推論 Benchmark

| 指標 | 說明 |
|------|------|
| `model_load_time_ms` | Checkpoint 載入到可推論狀態的時間 |
| `first_inference_ms` | 第一次推論（含 JIT/CUDA warmup） |
| `mean_inference_ms` | Warmup 後的平均推論延遲 |
| `std_inference_ms` | 延遲標準差 |
| `p95_inference_ms` | 第 95 百分位延遲（最差情況指標） |
| `throughput_fps` | 每秒處理幾張影像 |
| `gpu_memory_peak_mb` | GPU 記憶體峰值 |
| `output_hash` | 輸出影像的 SHA256（用於跨設備數值一致性檢查） |

目前 script 不再把 `checkpoint`、`test_input_dir`、`all_latencies_ms` 一起寫進結果 JSON，避免把本機絕對路徑和冗長原始 latency 陣列綁進已追蹤 artifacts。

### 訓練 Benchmark

| 指標 | 說明 |
|------|------|
| `epoch_times_sec` | 每個 epoch 的秒數 |
| `mean_epoch_time_sec` | 平均每 epoch 秒數 |
| `throughput_samples_per_sec` | 每秒處理幾個訓練樣本 |
| `gpu_memory_peak_mb` | 訓練時 GPU 記憶體峰值 |
| `total_time_sec` | 總訓練時間 |
| `mode` | "quick"（少量 epoch）或 "full"（完整訓練） |

### 數值一致性

跨設備比較會自動檢查 `output_hash`。如果不同設備的 hash 不同，代表浮點運算在不同 GPU / CPU 架構上有差異。這是正常的（不同硬體的浮點行為略有不同），但若差異持續擴大或只在某一台設備上出現，仍需要追查。

---

## 命令列參數

### run_inference_benchmark.py

```
--device DEVICE    指定設備（如 'cuda:0', 'cpu'），覆蓋 config
--warmup N         覆蓋 warmup 次數
--runs N           覆蓋 benchmark 次數
--no-cpu           跳過 CPU baseline
```

### run_training_benchmark.py

```
--device DEVICE    指定設備
--mode MODE        "quick" 或 "full"，覆蓋 config
--epochs N         覆蓋 epoch 數
--no-cpu           跳過 CPU baseline
```

### run_cross_device_compare.py

無需參數。自動讀取 `results/` 下所有設備的 JSON。

---

## 常見問題

### Q: 新設備上沒有訓練資料怎麼辦？

訓練 benchmark 在找不到真實資料時會自動使用合成資料（隨機 patch）。合成資料的 throughput 數字仍然有參考價值（量的是純 GPU 計算速度），但會低估真實訓練時間（少了磁碟 I/O 和影像前處理的開銷），且不能和使用真實資料的設備直接比較。

如果要量準確的訓練時間，需要把訓練集也帶過去：

| 目錄 | 本機路徑 | 大小 | 用途 |
|------|---------|------|------|
| `tra_src_ring/` | `Training_Data/tra_src_ring/` | ~333 MB | 訓練輸入影像 |
| `tra_lbl_ring/` | `Training_Data/tra_lbl_ring/` | ~333 MB | 訓練標籤影像 |

兩個目錄裡的檔名一一對應（如 `0001.bmp`、`0002.bmp`...）。複製到新設備後，在 `device_config.py` 裡設定：

```python
TRAINING_SRC_DIR = Path(r"/data/training/tra_src_ring")
TRAINING_LBL_DIR = Path(r"/data/training/tra_lbl_ring")
```

JSON 結果裡會標記使用了真實資料還是合成資料。

### Q: 可以在沒有 GPU 的機器上跑嗎？

可以。設定 `CUDA_DEVICE = None` 即可。推論和訓練都會走 CPU。但 CPU 非常慢，建議只跑推論 benchmark 且減少 runs：

```bash
python run_inference_benchmark.py --device cpu --runs 10
```

### Q: DEVICE_NAME 取什麼好？

建議格式：`GPU型號_辨識標記`。例如：
- `RTX3090_DesktopMain`
- `A100_CloudGPU0`
- `CPU_MacBookPro`
- `RTX4090_LabServer`

重點是**唯一**且**可辨識**。

### Q: 跑完 full mode 要多久？

取決於設備和訓練資料量。粗估：
- RTX 3090 + 真實資料：每 epoch 約 2-5 分鐘，100 epochs 約 3-8 小時
- CPU：非常慢，不建議跑 full mode

建議先跑 quick mode 看 per-epoch 時間，再決定要不要跑 full。

### Q: 怎麼加新的 benchmark 指標？

編輯 `scripts/run_inference_benchmark.py` 或 `run_training_benchmark.py`，在 `result` dict 裡加新欄位即可。`run_cross_device_compare.py` 只讀 JSON，不會因為多了欄位而壞掉。
