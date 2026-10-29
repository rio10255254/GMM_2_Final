# R130-Clean 建構、Scratch 訓練與驗收規格
## 目的
本文件用於交給 Codex，直接建立並乾淨執行下一版 MOSR 模型。此版本暫稱 **R130-Clean**。

R130-Clean 的目標不是重新發明整套 MOSR，也不是展開大量旁支消融，而是：
1. 保留 R129 已證明實用的核心精神：小型共享主幹、四次共享修正、同尺寸輸出、生成配對與位移一致性。
2. 恢復較接近 V42 的設計精神：**Raw 為主要影像基準，PSF 僅作為可選的弱光學輔助，不在輸入端強制改寫整張 Raw。**
3. 第一版完全關閉 PSF 路徑，先測試純神經網路在現有乾淨生成資料上的能力。
4. **所有神經網路權重必須從零初始化（scratch training）**，禁止載入 R129、R128、V42 或其他歷史模型權重。
5. 顯著降低 R129 的運算量與記憶體成本，尤其移除 2× CNN feature grid 與 4× internal state。
6. 保留日後將新校正 PSF 以 feature-level optical prior 接回的乾淨介面，但本次不啟用。
7. 所有流程必須可追查、可重跑、不可依賴不明歷史檔案或隱性 fallback。

---

# 1. 不可違反的總原則

## 1.1 本次不是大型架構搜索
不要同時測一堆版本。第一版只建立 **一個固定模型**，先快速完成乾淨訓練與正式驗收。

不要在本輪額外做：
- 1/2/3/4 次共享修正消融
- 多種 channel 數比較
- 多種 loss 比較
- 多種 PSF 方式比較
- 多模型排行榜
- 大量超參數搜索

第一版先把模型乾淨地做對、跑完、量測。

## 1.2 R129 作為概念基礎，不作為權重來源
R130-Clean 可以沿用 R129 的核心設計思路，但 **不能載入 R129 checkpoint**。

必須滿足：
- `checkpoint = None`
- `resume = False`
- `pretrained = False`
- `teacher = None`
- 不載入任何舊 model state dict
- 不載入任何舊 optimizer state
- 不載入任何舊 EMA state
- 不載入任何舊 learned step strength

程式啟動時必須明確輸出：

```text
TRAINING MODE: SCRATCH
Loaded pretrained parameters: 0
Loaded checkpoint: NONE
Loaded optimizer state: NONE
PSF mode: OFF
Real-image training data: NONE
SEM supervision: NONE
PI supervision: NONE
```

並寫入 `run_config.json`。

## 1.3 第一版 PSF 完全關閉
這不是把 PSF gain 設很小，而是 **完全不執行 PSF 路徑**。

本輪禁止：
- 讀取舊 PSF 檔
- 掃描 PSF 資料夾
- Wiener 反卷積
- FFT optical conditioning
- 平均 PSF
- 四候選 PSF
- PSF weighting network
- 歷史 SEM 衍生 optical kernel

如果 `optical_mode="off"`：
- 程式不得嘗試尋找 PSF
- 不得 silent fallback 到預設 PSF
- 不得從 checkpoint 或 config 偷帶 PSF

## 1.4 真實資料不得進入訓練
沿用目前乾淨生成資料。

訓練不得使用：
- 真實 Raw 影像
- SEM 影像
- SEM contour
- SEM 尺寸
- PI 回授值
- 現有 930 張正式實拍作為訓練 pair
- 現有正式量測結果作為模型選擇 loss

真實資料只在訓練完成後作正式驗證。

---

# 2. 模型設計目標

R130-Clean 要保留 R129 的「small shared iterative refinement」精神，但刪掉目前最可疑與昂貴的部分。

## 2.1 保留的 R129 核心
第一版保留：
- 64-channel 主幹
- 4 個 residual blocks
- dilation = `[1, 2, 4, 2]`
- 每個 residual block 兩個 3×3 conv
- SiLU 中間啟動
- 0.1 倍 residual block 內更新
- 4 次共享修正
- 四次修正共用同一套參數
- 每一步有獨立可學習 step strength
- 同尺寸輸入與輸出
- paired translation learning
- synthetic clean target
- image + gradient + pair 三項 loss

## 2.2 移除的 R129 設計
第一版移除：
- 輸入端 measured optical conditioning
- 25 PSF 平均
- 4 candidate PSF
- global PSF weighting MLP
- FFT / Wiener 路徑
- 2× feature grid
- 4× internal state
- 2×→4× bilinear upsampling
- 4× state 回原尺寸的 4×4 averaging
- 最後 `n - G*n` 的 high-pass 再加回 Raw
- image-wide quality score `q`
- 全域 signal/noise quality gain
- 任何 image-wide pooling / image-wide normalization
- GroupNorm
- 依整張圖統計決定修正量的機制

---

# 3. 新模型整體資料流

第一版固定使用：

```text
Raw x
  ↓
Native-resolution local feature construction
  ↓
Shared refinement block #1
  ↓
Shared refinement block #2
  ↓
Shared refinement block #3
  ↓
Shared refinement block #4
  ↓
Bounded residual relative to Raw
  ↓
Raw + bounded residual
  ↓
Native-size output y
```

PSF 介面保留但第一版完全關閉：

```text
Optional PSF feature branch
    └── optical_mode = "off"   # 本輪固定
```

---

# 4. Native-resolution 共享修正

## 4.1 不使用 2× / 4× 內部網格
所有主幹 feature 都保持與輸入相同 H×W。

若訓練輸入為 320×320：
- 主幹 feature 也是 320×320
- 不建立 640×640 主幹
- 不建立 1280×1280 state

這是本輪最重要的加速來源之一。

## 4.2 建議的 7-channel 輸入線索
保留 R129 的局部線索精神，但全部以 Raw `x` 與目前估計 `z_i` 建立：

\[
F_i = [
z_i,\;
x,\;
z_i-x,\;
\nabla_x x,\;
\nabla_y x,\;
\nabla^2 x,\;
\operatorname{Mean}_{5\times5}(x)
]
\]

共 7 channels。

定義：
1. `z_i`：目前第 i 次修正後的影像
2. `x`：Raw
3. `z_i - x`：目前相對 Raw 已修改多少
4. Raw horizontal gradient
5. Raw vertical gradient
6. Raw Laplacian
7. Raw 5×5 local mean

所有梯度與局部平均必須使用固定、可追查實作。

## 4.3 Shared backbone
固定：
- `Conv2d(7, 64, 3, padding=1)`
- 4 個 residual blocks
- dilation `[1,2,4,2]`
- 每個 block：
  - 3×3 conv
  - SiLU
  - 3×3 conv
  - `feature = feature + 0.1 * residual`
- 最後 `Conv2d(64, 1, 3, padding=1)`
- 輸出通過 `tanh`

禁止：
- BatchNorm
- GroupNorm
- LayerNorm over spatial field
- global pooling
- global mean/std conditioning
- attention 需要全圖 token mixing 的設計
- FFT

---

# 5. Raw-centered bounded residual 更新

這是 R130-Clean 與現有 R129 最重要的輸出差異。

## 5.1 初始化
\[
r_0 = 0
\]

\[
z_0 = x
\]

其中：
- `r_i` 是累積殘差
- `z_i` 是當前重建
- `x` 是 Raw

## 5.2 每一步更新
第 i 次：

\[
\Delta r_i = P_\theta(F_i)
\]

其中 `P_theta` 為四次共用的 shared backbone。

更新：

\[
r_i =
\operatorname{clip}
\left(
r_{i-1}
+ \eta_i \tanh(\Delta r_i),
-r_{\max},
r_{\max}
\right)
\]

\[
z_i =
\operatorname{clip}(x+r_i,0,1)
\]

## 5.3 Step strength
保留四個可學習 step strengths：

\[
\eta_i = \eta_{\max}\cdot \sigma(s_i)
\]

建議第一版：
- `eta_max = 0.25`
- 四個 `s_i` 為獨立可學習 scalar
- 初始化使 `eta_i` 不要過大

不要引入全域 quality gate。

## 5.4 Residual bound
保留整體 bounded residual。

建議第一版：
- `r_max` 可先採 R129 修正尺度附近的保守值
- 若目前程式有既有合理值，請直接沿用 R129 對輸出修正幅度的量級
- 不要重新做超參數 sweep

重要：
- `r=0` 時必須精確得到 `y=x`
- clear / identity case 必須有真正零修正的表示能力

## 5.5 最終輸出
\[
y=z_4
\]

不要再做：
- 高斯 high-pass extraction
- `n-G*n`
- global quality gain
- mean brightness recentering

若未來實拍發現全域亮度漂移，再另行處理；第一版保持最簡單、最可解釋。

---

# 6. Padding / Tile-safe 原則

本模型第一版就必須避免歷史模型的切塊依賴問題。

## 6.1 禁止 global operation
禁止：
- global pooling
- image-wide feature normalization
- image-wide mean/std gate
- global FFT
- 依 crop 大小改變行為的運算

## 6.2 Padding
使用固定 reflect padding。

不要在每個 tile 內任意重建不同邊界條件。

## 6.3 Inference
建立單一 inference path：
- full image
- tiled image

必須共用相同 model forward。

如需大圖切片：
- 固定 tile origin
- 固定 halo
- core-only output
- 不靠 feather blending 掩蓋模型差異

本輪不用做大量 tile 消融，但 runner 必須從架構上乾淨。

---

# 7. PSF 模組：本輪 OFF，但介面要先留好

## 7.1 API
模型保留：

```python
optical_mode = "off"
```

未來可擴充：

```python
optical_mode = "feature_single"
optical_mode = "feature_field"
```

本次禁止啟用後兩者。

## 7.2 未來 PSF feature branch 的設計原則
未來重新校正 PSF 後，考慮：

```text
Raw x
  ├── Main neural path
  │
  └── PSF-based optical cue
          ↓
      small local adapter
          ↓
      feature-level fusion
```

注意：
- PSF 不直接取代 Raw
- 不在輸入端強制做 Wiener conditioning
- optical feature adapter 預設零初始化
- optical gain 必須可以真正到 0
- PSF mode off 時完全不運算
- 未來優先使用「已知視野位置對應 PSF」而不是用整張亮度統計猜 PSF

本輪不實作正式 feature PSF，只留乾淨介面與 stub。

---

# 8. 訓練資料

直接沿用目前 R129 使用的乾淨生成資料分組。

固定母場景：
- train = 512
- dev = 128
- generated test = 128

類別：
- clear control
- lines / corners / junctions
- dense nearby structures
- flat-region control
- irregular curves
- noise control
- textured boundaries

每個來源具有：
- observed A
- clean target A
- observed shifted B
- clean target B
- known synthetic shift

沿用原本：
- source geometry
- degradation generation
- sensor area integration
- independent noise
- 8-bit quantization
- train/dev/test parent-scene separation

不要重新生成新資料，除非目前程式無法乾淨讀取既有資料。

---

# 9. 訓練輸入與 supervision

沿用目前：
- source native scene 384×384
- training crop 320×320
- central supervision core 128×128

保留真實 context，不要用 zero padding 或縮放假造上下文。

---

# 10. Loss

第一版固定不新增新 loss。

\[
L =
L_{\text{image}}
+0.2L_{\text{gradient}}
+0.2L_{\text{pair}}
\]

## 10.1 Image loss
沿用目前 R129 的 smooth robust grayscale loss：

\[
\rho(e)=
255\cdot
\operatorname{mean}
\left[
\frac{e^2}
{\sqrt{e^2+\epsilon^2}+\epsilon}
\right]
\]

\[
\epsilon=0.5/255
\]

其中：

\[
e = prediction - clean\ target
\]

## 10.2 Gradient loss
沿用目前 R129 定義：
- horizontal residual difference
- vertical residual difference
- 兩方向平均

## 10.3 Pair loss
沿用目前已知 synthetic shift。

比較：
- B 的 prediction residual
- A residual 按已知 shift 平移後的結果

配對 loss 不使用真實 PI。

無可觀測位移的 control case 不啟用 pair loss。

## 10.4 不加入
第一版不要加入：
- SEM loss
- PI loss
- CD loss
- contour loss
- SSIM
- perceptual loss
- FFT loss
- frequency weighting
- extra identity loss
- extra geometry loss
- dynamic loss weighting

---

# 11. Scratch Training Schedule

R129 接續訓練使用的低 learning rate 不適合 scratch。

第一版建議採用先前合成預訓練的 scratch 級 schedule：

- optimizer: AdamW
- max LR = `1e-3`
- min LR = `1e-5`
- warmup = `128 updates`
- cosine decay
- weight decay = `1e-5`
- gradient clipping = `5`
- FP32 第一版正式訓練
- 不使用舊 optimizer state

第一版先：
- 16 epochs
- 每 epoch 512 sources
- 總更新 = 8192

如果 dev loss 在 8192 仍明顯下降：
- 可以在同一 run 繼續
- 不另開新 model family
- 必須保留完整 continuation record

---

# 12. Random Seeds

固定並保存：
- model init seed
- data order seed
- noise seed

不要沿用會誤導成 R129 continuation 的 seed 名稱。

建議新建：
- model seed = 1309001
- order seed = 1309002
- noise seed = 1309003

若 Codex 認為需避免與舊記錄衝突，可採新的明確 R130 seed，但必須固定並寫入 config。

---

# 13. Checkpoint / Logging

## 13.1 Checkpoint
至少：
- every 128 updates 保存
- every 512 updates dev evaluation

保存：
- model state
- optimizer state
- update index
- epoch
- seeds
- git commit / source hash
- config hash

## 13.2 最終模型選擇
第一版固定使用最後 8192 update 作主要模型。

不要事後從中間 checkpoint 選一個最漂亮的真實影像結果。

dev curve 可用於確認訓練正常。

---

# 14. 訓練啟動前自動自查

建立 `preflight_check.py`，至少確認：

1. pretrained parameters count = 0
2. checkpoint path = None
3. optical mode = off
4. PSF files loaded = 0
5. SEM files used by dataset = 0
6. real Raw training images = 0
7. PI training labels = 0
8. train/dev/test parent IDs 無交集
9. model parameter count
10. one forward pass shape 正確
11. one backward pass 正常
12. no NaN / Inf
13. clear sample 可產生接近 Raw 的初始行為
14. full config 寫入 run folder

若任何條件不符：
- 直接停止
- 不要自動 fallback

---

# 15. 加速要求

這次加速不是旁支工作，是主模型需求。

## 15.1 第一版架構層級加速
已決定：
- 移除 2×主幹
- 移除 4×state
- 移除 2×→4×上採樣
- 移除高解析 64-channel upsampling
- 移除 PSF FFT
- 移除 global quality branch

預期主幹卷積空間工作量相對 R129 2× grid 大幅降低。

## 15.2 不先做危險低精度最佳化
第一個正式結果先用 FP32。

等模型功能確認後再測：
- BF16 / FP16
- TF32
- torch.compile
- CUDA Graph
- ONNX / TensorRT

不要把 mixed precision 與架構改版一起混成第一輪，避免無法判讀。

## 15.3 Profiling
第一版訓練完成後，對正式 inference 做一次 profiling。

至少分段：
- data transfer
- feature construction
- shared refinement ×4
- output
- tiled stitching
- total neural inference
- ACM / measurement（另外計）

記錄：
- full-image runtime
- tile runtime
- peak GPU memory
- parameter count

---

# 16. 程式結構

請建立全新獨立資料夾，不覆蓋 R129。

建議：

```text
R130_Clean/
├─ README.md
├─ model_r130_clean.py
├─ train_r130_clean.py
├─ infer_r130_clean.py
├─ dataset_r130_clean.py
├─ losses_r130_clean.py
├─ config_r130_clean.yaml
├─ preflight_check.py
├─ profile_r130_clean.py
├─ evaluate_generated.py
├─ evaluate_real_measurement.py
├─ optical/
│  ├─ interface.py
│  └─ disabled.py
├─ runs/
└─ reports/
```

不要直接修改原 R129 程式。

---

# 17. 必須產出的 README

README 必須明確寫：

## Model identity
- model = R130-Clean
- scratch training
- no pretrained neural weights
- PSF disabled
- synthetic-only neural training
- native-resolution shared refinement
- 4 shared updates
- Raw-centered bounded residual

## Training data
- 512 / 128 / 128
- no real images
- no SEM training
- no PI training

## Training
- optimizer
- LR schedule
- loss
- epochs / updates
- seeds

## Inference
- same-size output
- tile-safe design
- optical off

## Known scope
- first pure-ML clean baseline
- future PSF feature branch not enabled

---

# 18. 完成訓練後的最小正式驗收

不要做大量旁支實驗。

只做以下正式驗收。

## 18.1 Generated dev / test
報：
- total objective
- image loss
- gradient loss
- pair loss
- training curve
- dev curve

確認：
- 正常收斂
- 沒有 NaN
- 後段沒有發散

## 18.2 現有 930 張真實 Raw
用相同 930 張資料跑 R130-Clean。

固定：
- 同一九顆
- 同一 Raw tracking
- 同一 ACM
- 同一 maximum-gradient edge
- 同一 LSC
- 同一尺度
- 同一 PI 計算

禁止為新模型改 measurement backend。

## 18.3 正式比較只要
- Raw
- R129
- R130-Clean

本輪不用其他模型。

## 18.4 必須輸出的量測結果
至少：
1. adjacent step mean absolute PI difference
2. adjacent repeat SD
3. start-relative mean absolute PI difference
4. start-relative repeat SD
5. diameter repeatability
6. contour repeatability
7. de-mean-radius shape repeatability
8. SEM average diameter difference
9. full radial SEM difference
10. de-size shape SEM difference

目的：
- 看 pure ML 是否保留 R129 的穩定度優勢
- 看尺寸偏大的問題是否自然改善
- 不預設結果一定改善

## 18.5 Runtime
同時記錄：
- full image runtime
- peak VRAM
- parameter count

這次速度是正式結果之一。

---

# 19. 結果判讀原則

不要用單一指標選模型。

第一版主要看：
- R130-Clean 是否接近或保留 R129 的位移穩定度
- contour repeatability 是否仍明顯改善 Raw
- diameter / SEM bias 是否比 R129 更合理
- runtime 是否大幅改善
- 是否無明顯 halo / dark outline / fake edge

如果：
- 位移略退一點但速度大幅改善、尺寸 bias 大幅改善，也值得保留
- 視覺更銳利但 SEM / contour 更差，不算成功
- 重拍更穩但所有形狀被過度平滑，不算成功

---

# 20. PSF 重校正與新模型的關係

PSF 重校正與 R130-Clean scratch training 可平行進行。

本輪 R130-Clean：
- PSF OFF
- 不等 PSF
- 不依賴 PSF

明天新的 PSF calibration package 完成後：
- 先獨立確認其來源、倍率、尺度、方向與日期
- 不直接覆蓋歷史 PSF
- 不直接塞進 R130-Clean input
- 後續再建立 feature-level optical branch

新 PSF 不自動等於舊 930 張影像拍攝當時的正確 PSF。

---

# 21. 未來 Phase 2：PSF feature-level 輔助（本輪不要做）

等 pure-ML R130-Clean 結果完成後，若需要再做：

\[
d_{\text{psf}} = W_h(x)-x
\]

但只轉成 optical feature：

```text
PSF optical cue
    ↓
small local conv adapter
    ↓
feature fusion
```

禁止：
- 直接改寫 Raw
- input-side mandatory Wiener
- global PSF MLP guessing from mean/std
- optical gain 不能關閉

建議：
- adapter zero initialization
- optical gain 可精確為 0
- optical mode off 時 forward 完全跳過
- 若有視野座標，優先直接使用對應 PSF

---

# 22. Codex 執行順序

請按以下順序，不要跳步。

### Step 1：只讀取現有 R129 程式與資料介面
理解：
- dataset format
- current 7 cues
- current shared backbone
- current loss
- current train/dev split
- current evaluation interface

不要修改原檔。

### Step 2：建立全新 R130_Clean 目錄
複製必要的乾淨資料 loader 與 evaluation interface。

### Step 3：建立 native-resolution model
依本文件建立。

### Step 4：建立 scratch preflight
確認所有舊權重與 PSF 都沒有進來。

### Step 5：跑 1 batch smoke
確認：
- forward
- backward
- loss
- GPU memory
- output range
- identity behavior

### Step 6：跑小型短訓練 sanity check
例如 32–128 updates，只確認程式正常。

不要用真實正式資料挑架構。

### Step 7：正式 8192 update
固定設定一次跑完。

### Step 8：保存最終權重與完整 provenance

### Step 9：generated dev/test evaluation

### Step 10：930 張真實正式推論

### Step 11：跑既有 ACM / PI / SEM 評估

### Step 12：runtime / VRAM profiling

### Step 13：輸出完整報告

---

# 23. 最終交付物

Codex 最後必須提供：

1. `R130_Clean/` 完整程式
2. 最終 `run_config.json`
3. source hashes
4. final checkpoint hash
5. parameter count
6. training curve
7. dev curve
8. generated test summary
9. 930-image reconstruction output
10. Raw / R129 / R130-Clean measurement comparison
11. runtime report
12. peak VRAM report
13. `TRAINING_PROVENANCE.md`
14. `R130_CLEAN_RESULTS.md`

---

# 24. TRAINING_PROVENANCE.md 必須明確回答

- 是否從零訓練？ → YES
- 載入舊神經權重？ → NO
- 載入舊 optimizer？ → NO
- 使用 PSF？ → NO
- 使用 SEM train labels？ → NO
- 使用 PI train labels？ → NO
- 使用真實影像訓練？ → NO
- 使用 synthetic data？ → YES
- train/dev/test parent overlap？ → NO
- 最終模型 update？ → 明確數值
- 最終 checkpoint SHA256？ → 明確數值

---

# 25. 絕對禁止事項

Codex 不可以：
- 覆蓋 R129
- 覆蓋既有正式結果
- 自動選一個未知 PSF
- 因缺 PSF 而 fallback 到舊 PSF
- 偷載 pretrained checkpoint
- 偷載 optimizer
- 以真實 930 張資料做 gradient update
- 用 SEM / PI 做 training loss
- 為了結果好看改 ACM 或尺度
- 用新的 measurement backend 只給 R130
- 事後挑中間 checkpoint 只因真實資料最好
- 同時偷偷改資料生成與模型，除非原 loader 無法使用且有明確紀錄
- 將速度提升靠降低正式影像尺寸而不註明
- 將 ROI runtime 與 full-image runtime 混寫

---

# 26. 本版本的核心定位

R130-Clean 應被理解為：

> A clean-scratch, native-resolution, shared-iterative, Raw-centered MOSR reconstruction model trained only with existing synthetic paired data, with explicit optical correction disabled in the first stage.

中文：

> **R130-Clean 是一個從零訓練、原尺寸運算、共享多次修正、以 Raw 為核心的 MOSR 重建模型。第一階段僅使用既有生成配對資料進行學習，不載入歷史神經權重，也不啟用顯式 PSF 光學修正。模型保留 R129 的共享反覆重建精神，但移除高成本內部上採樣與全域光學前處理，使架構更乾淨、可控且適合後續重新導入經確認的 feature-level PSF 先驗。**
