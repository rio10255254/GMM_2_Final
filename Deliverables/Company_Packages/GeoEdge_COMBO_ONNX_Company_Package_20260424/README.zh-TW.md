# GeoEdge COMBO ONNX 公司端部署套件

> 版本代號：`GeoEdge_COMBO_ONNX_Company_Package_20260424`
> 模型基準：`COMBO / r38v2_8px_gate_p95`
> 來源 Checkpoint：`best_tradeoff.pth.tar`（epoch 21）
> 匯出工具：PyTorch 2.3.0 → ONNX opset 17

---

## 一、套件目的

本資料夾為 **GeoEdge COMBO** 影像強化模型的 **ONNX 公司端部署版本**，目的是讓接收端不需要安裝 PyTorch、不需要 GPU、不需要存取訓練程式庫，即可使用最小依賴重現生產基準的推論結果。

主要特點：

- **最小依賴**：僅需 `numpy`、`onnxruntime`、`opencv-python` 三個 Python 套件。
- **純 CPU 推論**：固定使用 `CPUExecutionProvider`，部署環境無 GPU 也能運作。
- **動態輸入形狀**：ONNX 模型支援任意 batch、任意 H/W（會自動 pad 到 8 的倍數）。
- **保留輸入規格**：輸出影像會與輸入維持相同的 shape 與 dtype。
- **可重現驗證**：附上與完整 PyTorch 推論結果的 PSNR 對比（≈ 64.77 dB）。

---

## 二、檔案結構

```
GeoEdge_COMBO_ONNX_Company_Package_20260424/
├── README.md                         # 英文版說明
├── README.zh-TW.md                   # 本檔案（繁體中文詳細版）
├── MANIFEST.json                     # 套件檔案清單
├── requirements.txt                  # Python 相依套件清單
├── run_combo_onnx.py                 # 推論執行器（核心腳本）
├── verification_report.json          # 與完整 PyTorch 的差異驗證報告
│
├── model/
│   └── geoedge_combo_body.onnx       # 神經網路本體（約 16 MB）
│
├── assets/
│   ├── preprocess_config.json        # 前處理常數（reg / alpha / align_factor）
│   └── psf_mean.npy                  # 點擴散函數 PSF 平均（101×101 float32, sum=1）
│
├── samples/
│   ├── sample_input.bmp              # 範例輸入（512×512 灰階 BMP）
│   ├── sample_output_onnx.bmp        # 本套件 ONNX 推論結果
│   └── sample_output_reference_pytorch.bmp  # 完整 PyTorch 參考結果
│
├── tests/
│   └── test_package_smoke.py         # pytest 冒煙測試
│
└── outputs/                          # 預設輸出目錄（初始為空）
```

---

## 三、安裝步驟

### 3.1 系統需求

- **Python**：3.9 以上（建議 3.10 或 3.11）
- **作業系統**：Windows / Linux / macOS 皆可
- **硬體**：CPU 即可，建議至少 4 GB 可用記憶體

### 3.2 安裝相依套件

開啟終端機，切換到本套件根目錄後執行：

```bash
python -m pip install -r requirements.txt
```

`requirements.txt` 內容如下：

```
numpy
onnxruntime
opencv-python
```

如有需要可另外指定版本，例如：

```bash
python -m pip install "onnxruntime>=1.17,<2.0"
```

---

## 四、快速開始

### 4.1 單張影像推論

```bash
python run_combo_onnx.py --input samples/sample_input.bmp --output outputs
```

執行後會在 `outputs/` 目錄產生 `sample_input.bmp`，可與 `samples/sample_output_onnx.bmp` 比對應為近似一致。

### 4.2 整個資料夾批次推論

```bash
python run_combo_onnx.py --input path/to/images --output outputs
```

支援的影像副檔名：`.bmp`、`.png`、`.tif`、`.tiff`、`.jpg`、`.jpeg`。

### 4.3 自訂模型 / 設定路徑（進階）

預設會自動尋找套件內的 model 與 assets，但你也可以手動指定：

```bash
python run_combo_onnx.py \
  --input samples/sample_input.bmp \
  --output outputs \
  --model model/geoedge_combo_body.onnx \
  --config assets/preprocess_config.json \
  --psf assets/psf_mean.npy
```

### 4.4 命令列參數總覽

| 參數 | 必填 | 預設值 | 說明 |
|------|------|--------|------|
| `--input` | ✅ | — | 單張影像路徑或包含多張影像的資料夾 |
| `--output` | ✅ | — | 輸出資料夾（不存在會自動建立） |
| `--model` | ❌ | `model/geoedge_combo_body.onnx` | ONNX 模型路徑 |
| `--config` | ❌ | `assets/preprocess_config.json` | 前處理參數 JSON |
| `--psf` | ❌ | `assets/psf_mean.npy` | PSF 資料 |

---

## 五、推論流程詳解

`run_combo_onnx.py` 內的 `run_one()` 是整個推論流程的核心，可拆解為以下五個步驟：

### 步驟 1：讀取影像（`imread_unicode`）

使用 `np.fromfile` + `cv2.imdecode` 讀檔，避免 OpenCV 對含中文 / 非 ASCII 路徑的支援問題。彩色影像會自動以 `cv2.cvtColor(BGR2GRAY)` 轉成灰階。

### 步驟 2：歸一化到 [0, 1]（`normalize_to_01`）

依輸入 dtype 自動處理：

- **整數型別**（uint8、uint16…）：以 `np.iinfo` 取得型別範圍，線性映射到 `[0, 1]`。
- **浮點型別**：若最大值大於 1.5 視為 0–255 的浮點，除以 255；否則視為已經在 0–1。

並把原始 dtype 記下來，最後輸出時會還原。

### 步驟 3：對齊到 8 的倍數（`pad_to_multiple`）

模型需要 H/W 為 8 的倍數（呼應基準名稱 `8px_gate`）。若不足，會以 `mode="reflect"` 在右側與下方補齊；輸出時會再裁回原始尺寸。

### 步驟 4：物理前處理（`physics_preprocess`，**重點**）

這是一段 **Wiener 風格的 FFT 反卷積（deconvolution）**，做法如下：

1. 將 101×101 的 PSF 以 zero-pad 補齊至輸入影像大小，並將其置中。
2. 對輸入影像與 padded PSF 各做一次 `np.fft.rfft2`。
3. 構造維納濾波器：

   ```
   H(u, v) = conj(PSF_F) / (|PSF_F|² + reg + 1e-6)
   ```

   其中 `reg = 10.0`（從 `preprocess_config.json` 讀取）。
4. 在頻域相乘後 `irfft2` 回到空間域，再做 `clip(-100, 100)` 防溢位。
5. 與原圖做線性混合：

   ```
   x_phys = x + α · (deconv − x)
   ```

   其中 `α = 0.10001027584075928`（同樣來自 config）。

> **為什麼這段不放進 ONNX？** PyTorch ONNX exporter 目前無法把 FFT 操作完整放進單一 ONNX 圖中，因此將這段物理前處理留在 Python 端，神經網路本體則放進 ONNX。完整原始模型還包含一個 `weak_psf_block`，因實測影響極小（量化結果見驗證報告），故未匯出。

### 步驟 5：ONNX 推論與還原

```python
session.run(None, {"input": x_phys[None, None, :, :]})  # NCHW
```

推論輸出 `clip(0, 1)`，再裁回原始 H×W，最後依原 dtype 還原：

- **整數**：`np.rint` 四捨五入到最近整數，並 clip 到型別範圍內。
- **浮點**：保留 `float32`。

最終以 `imwrite_unicode` 寫檔（同樣支援中文路徑）。

---

## 六、模型身份與來源

| 項目 | 內容 |
|------|------|
| 生產基準 (Production baseline) | COMBO / `r38v2_8px_gate_p95` |
| 來源 checkpoint | `training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260408_003525/weights/best_tradeoff.pth.tar` |
| Best epoch | 21 |
| Tradeoff score | -4.601281688761959 |
| Opset | 17 |
| Producer | PyTorch 2.3.0 |
| 模型節點數 | 352 |
| 主要算子 | Conv ×33、InstanceNormalization ×23、Sigmoid ×24、Resize ×3 |
| ONNX checker | passed |

ONNX 模型本體大小約 **16 MB**，輸入 / 輸出規格如下：

```
Input  : float32 NCHW grayscale  shape=[batch, 1, H, W]   (H, W 必須為 8 倍數)
Output : float32 NCHW grayscale  shape=[batch, 1, H, W]   range=[0, 1]
```

---

## 七、前處理常數說明（`preprocess_config.json`）

| 鍵 | 值 | 說明 |
|-----|-----|------|
| `align_factor` | `8` | 模型要求的 H/W 對齊倍數 |
| `physics_reg` | `10.0` | Wiener 反卷積的正則化常數 |
| `physics_alpha` | `0.10001027584075928` | 反卷積結果與原圖的混合比例 |
| `physics_psf` | `assets/psf_mean.npy` | PSF 檔案路徑 |
| `onnx_model` | `model/geoedge_combo_body.onnx` | ONNX 模型路徑 |
| `output_rounding` | `nearest integer via np.rint` | 整數型別輸出時的捨入規則 |
| `omitted_from_onnx` | `weak_psf_block` | 未匯出 ONNX 的弱 PSF 區塊（影響極小，見驗證報告） |

PSF 資訊：shape=`(101, 101)`、dtype=`float32`、sum=`1.0`、mean≈`9.8e-5`、max≈`7.7e-3`。

---

## 八、驗證報告（`verification_report.json`）

範例輸入來源：

- 原圖：`C:\Users\Rio\Downloads\NTU_ImageDataset\Pitch1um_Y_100\Cropped_Output\VisionTop_20251029182653732.bmp`
- 裁切：top=834, left=504, height=512, width=512

ONNX vs 完整 PyTorch（uint8 比較）：

| 指標 | 數值 | 解讀 |
|------|------|------|
| 平均絕對誤差 (mean abs gray level) | **0.0217** | 平均每像素僅差 0.02 個灰階 |
| 最大絕對誤差 (max abs gray level) | **1.0** | 最差也只差 1 個灰階 |
| **PSNR** | **64.77 dB** | 視覺上幾乎無差異（一般 > 40 dB 就視為高品質） |

備註：

- ONNX 模型僅包含主神經網路本體。
- PSF 物理前處理由 `run_combo_onnx.py` 在 Python 端執行。
- `weak_psf_block` 未匯出，但範例層級的影響已涵蓋於上述 PSNR 評估中。

---

## 九、自動化測試

`tests/test_package_smoke.py` 是一份 pytest 冒煙測試，會做下列檢查：

1. 確認模型、設定、PSF、範例圖、執行腳本都存在。
2. 用 `subprocess` 實際呼叫 `run_combo_onnx.py` 推論範例圖。
3. 驗證：
   - 程式 `returncode == 0`
   - 輸出檔確實存在
   - **輸出 shape 與 dtype 必須與輸入一致**（部署正確性的硬性合約）

執行方式：

```bash
python -m pip install pytest
python -m pytest tests/ -v
```

---

## 十、進階用法

### 10.1 在 Python 中以函式方式呼叫

如果你想嵌入到自家管線而不是用 CLI，可以直接 import：

```python
from pathlib import Path
import json, numpy as np, onnxruntime as ort
from run_combo_onnx import run_one

config = json.load(open("assets/preprocess_config.json", "r", encoding="utf-8"))
psf_mean = np.load("assets/psf_mean.npy").astype(np.float32)
session = ort.InferenceSession("model/geoedge_combo_body.onnx",
                               providers=["CPUExecutionProvider"])

run_one(session, psf_mean, config,
        Path("input.bmp"), Path("outputs/input.bmp"))
```

### 10.2 切換到 GPU（若環境允許）

預設使用 CPU。若你已安裝 `onnxruntime-gpu` 並具備合適的 CUDA 環境，可在自家程式中改成：

```python
session = ort.InferenceSession(
    "model/geoedge_combo_body.onnx",
    providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
)
```

注意：本套件 `requirements.txt` 預設是 `onnxruntime`（CPU 版），若要 GPU 需自行安裝 `onnxruntime-gpu`。

### 10.3 處理超大影像

由於 `physics_preprocess` 對整張影像做 FFT，記憶體消耗會隨影像面積線性成長。對於非常大的影像，建議：

- 切片處理（tile），每塊保留至少 PSF 一倍以上的 overlap 以避免邊界效應，再以 feathered blending 拼回。
- 或評估改用較小的 `align_factor` 倍數區塊。

---

## 十一、輸入 / 輸出規格

### 輸入影像

- **格式**：BMP / PNG / TIFF / JPEG
- **通道**：灰階（彩色會自動轉灰階）
- **尺寸**：任意（小於 PSF 尺寸 101×101 的影像會直接報錯）
- **dtype**：任何整數或浮點

### 輸出影像

- **檔名**：與輸入同名，存放於 `--output` 指定資料夾
- **shape**：與輸入完全一致
- **dtype**：與輸入完全一致
- **整數輸出**：使用 `np.rint` 四捨五入

---

## 十二、常見問題（FAQ）

**Q1：執行時出現「Failed to read image」？**
請確認路徑正確且檔案實際存在；本套件已使用 `np.fromfile` 處理含中文路徑，但檔案損毀仍會失敗。

**Q2：執行時出現「PSF size 101x101 exceeds input size HxW」？**
輸入影像太小（兩邊都需 ≥ 101 像素）。請使用較大尺寸的影像。

**Q3：ONNX Runtime 啟動很慢？**
首次載入 ONNX 模型會做 graph 最佳化，第一次大約需要數秒。後續呼叫同一個 `InferenceSession` 不會再重複此成本，建議在自家程式中重用 session。

**Q4：輸出與 `samples/sample_output_onnx.bmp` 不完全一致？**
應該要 bit-for-bit 一致（同樣的 ONNX、同樣的 PSF、同樣的 config），如有差異請檢查：

- 是否使用了不同版本的 `numpy` 或 `onnxruntime`（FFT / BLAS 實作差異可能造成最後一個 LSB 的差別）。
- 是否誤改了 `preprocess_config.json` 或 `psf_mean.npy`。

**Q5：可以拿來商用嗎？**
請依貴司與模型擁有者的授權條款處理；本 README 不涵蓋授權聲明。

---

## 十三、版本資訊

- **套件版本**：`GeoEdge_COMBO_ONNX_Company_Package_20260424`
- **建立來源 repo**：`D:\GMM_2_Final`
- **建立日期**：2026-04-24
- **本 README 撰寫日期**：2026-04-28

---

## 十四、聯絡與回報

若推論結果與驗證報告差異過大、或在特定影像上發現異常輸出，請保留以下資訊以利除錯：

1. 觸發問題的輸入影像（或裁切後的最小重現樣本）。
2. 完整命令列與終端機輸出。
3. `python -c "import numpy, onnxruntime, cv2; print(numpy.__version__, onnxruntime.__version__, cv2.__version__)"` 的輸出。
4. 作業系統與 Python 版本。
