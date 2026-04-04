# R26 分析總覽

## 模型資訊

| 項目 | 值 |
|------|------|
| 模型名稱 | GESR_v1_v5_ST0p8_SWP_r26sm035 |
| 簡稱 | R26 |
| PSF 類型 | Whole-FOV PSF（10x10 grid 空間相依反卷積核） |
| Checkpoint | r26_sm035（smooth 0.35，最佳 tradeoff） |
| 角色 | 正式交付版，用於 GeoEdge 產線驗證 |

## 什麼是 Whole-FOV PSF

傳統 PSF 假設整張影像的模糊模式相同（空間不變）。但顯微鏡的光學系統在視野（FOV）的不同位置會有不同的像差，特別是在邊緣區域。Whole-FOV PSF 把視野切成 10x10 的 grid，每個 grid cell 有自己的 PSF kernel，反卷積時根據像素位置選擇對應的 kernel。這讓 R26 能在整個視野上都有正確的反卷積。

## 最終驗收指標

> **外部 GMF 在 0.8px pitch 序列上的 step_std < 0.167862**（Round30 baseline）

- **step_std**：幀間位移標準差。理想的恆定步長序列中，每步位移應完全相同，step_std = 0 就是完美。
- **0.167862**：Round30 某個 checkpoint 達到的 step_std，作為 R26 需要打敗的 baseline。
- **GMF**：Geometric Matching Feature，GeoEdge 的全環模板匹配演算法，是計算 step_std 的最終標準。

### 目前狀態

| 尺度 | GMF step_std | Baseline | 判定 |
|------|-------------|----------|------|
| 8px（1 μm） | 0.201 | 0.205 | **達標** |
| **0.8px（0.1 μm）** | **0.191** | **0.168** | **未達標（差 14%）** |
| 0.08px（0.01 μm） | 0.180 | 0.158 | **未達標（差 14%）** |

R26 在 8px 大步長上已達標，但在 0.8px 主戰場上差距 14%。瓶頸已從「邊界模糊」轉移到「殘差噪聲地板」——R26 的反卷積品質是好的，但還不夠好到讓亞像素定位精度突破 baseline。

## 兩條分析線

### `single_image/` — 單張影像幾何分析

**問的問題**：R26 重建有沒有真的改善邊界的幾何品質？改善了多少？有沒有引入新的偽影？

**怎麼分析**：取一張 demo 影像，用 360 個角度的邊緣提取 + 圓擬合 + DFT 諧波分解 + 能量拆分 + 熱點聚集分析，逐一量化 input 和 output 的幾何差異。

**核心發現**：

| 指標 | Input | Output | 改善 |
|------|-------|--------|------|
| 外邊界殘差 std | 6.45 px | 2.63 px | 59.2% |
| 內邊界殘差 std | 6.25 px | 2.95 px | 52.8% |
| 外邊界邊緣寬度（10-90%） | 35.6 px | 22.6 px | 36% |
| 圓心偏移（內外不一致） | 0.31 px | 0.75 px | 偏移增加（固定偏置） |
| 內邊界主導諧波模式 | k=4 | k=2（橢圓） | 需序列驗證 |

**留下的問題**：單張只能看到一幀的 snapshot，無法回答「這些數字在幀間穩定嗎」、「k=2 是固定的還是隨機的」等時間穩定性問題。→ 交給 `sequence/`。

### `sequence/` — 多幀序列穩定性分析

**問的問題**：單張分析發現的改善和偏差，在連續多幀中是否穩定？會不會在某些幀突然惡化？

**怎麼分析**：用三個不同 pitch 步長的連續 Y 方向位移序列（共 203 幀），逐幀跑完整的幾何分析，然後計算序列統計量——步進穩定性、k=2 幀間 CV%、圓心偏移漂移趨勢、殘差改善一致性、高殘差角度持續性。

**核心發現**：五個時間穩定性問題全部得到正面裁決：

| 問題 | 裁決 |
|------|------|
| 改善是否幀間穩定？ | **穩定**（std 2.4-3.9%，min 44.9%，無退步幀） |
| k=2 橢圓模式固定 or 波動？ | **固定偏置**（CV < 16%，phase std < 7°） |
| 圓心偏移固定 or 漂移？ | **固定偏置**（std/mean < 0.25） |
| 殘差改善在所有幀成立？ | **是**（min 44.9%，max 76.2%） |
| 高殘差角度幀間固定？ | **固定**（21-33 角度 >50% 幀持續，max_persistence = 1.0） |

### `performance/` — 跨設備效能基準測試

**問的問題**：R26 在不同設備上的推論速度和訓練速度差多少？不同 GPU 的數值結果是否一致？

**怎麼分析**：在每台設備上跑標準化的推論 benchmark（warmup + 多輪計時）和訓練 benchmark（quick/full 兩種模式），量化延遲、吞吐量、GPU 記憶體峰值，並用 output hash 檢查跨設備的數值一致性。

**核心量測**：

| 類別 | 指標 |
|------|------|
| 推論 | 平均延遲、P95 延遲、FPS、GPU 記憶體峰值 |
| 訓練 | 每 epoch 時間、samples/sec、GPU 記憶體峰值 |
| 一致性 | output SHA256 hash 跨設備比對 |

**使用方式**：只改 `configs/device_config.py` 裡的路徑和設備名，跑腳本即可。詳見 `performance/README.md`。

## 三條分析線的關係

```
single_image（靜態品質）──── 發現問題 ────→ sequence（時間穩定性）──── 確認安全性
     │                                           │
     └── 提供核心分析函式 ─── importlib 載入 ────→┘

performance（效能基準）──── 獨立分析線，不依賴上面兩條
```

- 邏輯上：`single_image` 先跑，找出「看起來不錯但需要確認」的指標，`sequence` 再用多幀驗證
- 程式碼上：`sequence/scripts/run_sequence_analysis.py` 透過 `importlib` 動態載入 `single_image/scripts/run_single_image_analysis.py` 中的核心函式
- `performance` 是獨立分析線，直接 import `Model/` 下的模型和推論函式，不依賴 `single_image` 或 `sequence`

## 如何執行

```bash
# 單張分析（自含，不需要外部資料）
python AnalysisLab/r26/single_image/scripts/run_single_image_analysis.py

# 序列分析（需要外部資料路徑可達）
python AnalysisLab/r26/sequence/scripts/run_sequence_analysis.py

# 效能 benchmark（先改 configs/device_config.py 裡的路徑）
python AnalysisLab/r26/performance/scripts/run_inference_benchmark.py
python AnalysisLab/r26/performance/scripts/run_training_benchmark.py
python AnalysisLab/r26/performance/scripts/run_cross_device_compare.py

# 測試
pytest AnalysisLab/r26/single_image/tests/ -q   # 5 tests
pytest AnalysisLab/r26/sequence/tests/ -q        # 8 tests
pytest AnalysisLab/r26/performance/tests/ -q     # 4 tests
```
