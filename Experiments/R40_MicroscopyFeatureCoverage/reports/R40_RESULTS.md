# R40 結果 — 顯微特徵覆蓋

狀態：訓練、local 分析、外部 GMF 都跑完。R40 是成功的 capacity study，但**不是**升級候選——guarded 權重平均候選讓 8px 外部 ring guard 退步。

## 目的

R40 是 microscopy 特徵的 capacity 試探。它接 R39 的發現：COMBO 與 R39 a030 對單純合成形狀重建得不錯，但兩者都把訓練分布外的 grid 與紋理 microscopy 特徵抹掉。

R40 擴大受控合成訓練分布，不加真實影像、不動模型本體。

## 已完成項目

- 建立 `R40_MicroscopyFeatureCoverage` 實驗目錄結構。
- 五個 microscopy 特徵家族的乾淨合成資料產生器：
  - line / grid 結構
  - 大塊 IC 風格區域
  - 顆粒狀與低對比紋理
  - 不規則邊緣 defect
  - 混合 microscopy 場景
- 加上 source / label 配對檢查的 train / validation 包 builder。
- split 驗證：確保訓練包與 held-out microscopy 驗證包不重疊。
- 兩個候選的 launcher：
  - `r40_micro_capacity_combo`
  - `r40_micro_capacity_a030`
- microscopy 特徵重建指標：
  - PSNR / SSIM
  - high-frequency retention
  - edge retention
  - contrast retention
- 用既有 720-angle 分析器做 local ring guard 入口。
- 訓練後 COMBO ↔ R40 trade-off 搜尋的權重平均 sweep 邏輯。
- 最終三尺度 guard 用的外部 GMF parser 與 verdict 助手。
- 資料生成、split 安全性、metric、權重 sweep 邏輯、外部 GMF parsing 的單元測試。

## 候選路線

| Candidate | 起點 checkpoint | 角色 |
|---|---|---|
| `r40_micro_capacity_combo` | COMBO | 主要 capacity 探針 |
| `r40_micro_capacity_a030` | R39 a030 | 看 R39 形狀 prior 對 microscopy 特徵有沒有幫助 |

## 必過的檢查

R40 訓練前的 setup 與 baseline 解讀檢查：

| 檢查項 | 狀態 |
|---|---|
| 產 R40 乾淨 label | COMPLETE |
| 對 stage 29–33 跑 PSF convolution | COMPLETE |
| Build `r40_micro_capacity_train` 與 `micro_val_unseen` | COMPLETE |
| 驗 train / held-out microscopy split 不重疊 | COMPLETE |
| 在 `micro_val_unseen` 上跑 COMBO baseline | COMPLETE |
| 在 `micro_val_unseen` 上跑 R39 a030 baseline | COMPLETE |
| 訓練兩個 R40 候選 | COMPLETE |
| 跑 R40 候選的 microscopy 特徵驗證 | COMPLETE |
| 跑 R40 候選的 local 三尺度 ring guard | COMPLETE |
| 端點若 microscopy 特徵進步但 ring 退步，跑 COMBO 權重平均 | COMPLETE |
| 只把過 local guard 的權重平均候選送外部 GMF | COMPLETE；`r40_combo_best_avg_a045` 在外部 8px 退步，僅作研究紀錄 |

## 已 build 的資料包

build 日期：2026-05-03。

| Profile | 配對總數 | 組成 |
|---|---:|---|
| `r40_micro_capacity_train` | 1300 | 550 ring replay、350 R39 shape replay、400 R40 microscopy 特徵 |
| `micro_val_unseen` | 100 | 五個 R40 microscopy 特徵家族各 20 對 held-out |

split 驗證結果：`disjoint`。

## Baseline microscopy 驗證

任何 R40 訓練之前，先在 `micro_val_unseen` 上跑 baseline。

| Model | Avg PSNR | Avg SSIM | High-frequency retention | Edge retention | Contrast retention |
|---|---:|---:|---:|---:|---:|
| COMBO | `22.7326` | `0.8588` | `0.2234` | `0.6607` | `0.8857` |
| R39 a030 | `25.0323` | `0.8904` | `0.2206` | `0.6181` | `0.9252` |
| Delta a030 − COMBO | `+2.2997` | `+0.0317` | `−0.0027` | `−0.0426` | `+0.0395` |

逐特徵比較：

| 特徵家族 | COMBO PSNR | a030 PSNR | PSNR delta | COMBO HF | a030 HF | HF delta | COMBO edge | a030 edge | Edge delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Lines / grid | `17.7067` | `18.3261` | `+0.6194` | `0.0506` | `0.0913` | `+0.0407` | `0.2276` | `0.2895` | `+0.0618` |
| Large regions | `23.1418` | `26.6334` | `+3.4916` | `0.3719` | `0.3275` | `−0.0443` | `1.2005` | `0.9933` | `−0.2072` |
| Textures | `27.0644` | `28.2059` | `+1.1415` | `0.1478` | `0.3028` | `+0.1550` | `0.5770` | `0.7470` | `+0.1700` |
| Edge defects | `23.8592` | `27.5255` | `+3.6663` | `0.3933` | `0.1824` | `−0.2109` | `1.0695` | `0.8461` | `−0.2233` |
| Mixed fields | `21.8909` | `24.4705` | `+2.5796` | `0.1533` | `0.1991` | `+0.0458` | `0.2290` | `0.2149` | `−0.0142` |

代表性視覺對比：
`Experiments/R40_MicroscopyFeatureCoverage/results/micro_recon/r40_baseline_micro_comparison.png`

## Baseline 解讀

R39 a030 不只是形狀泛化結果。在 R40 held-out microscopy 特徵集上，它 PSNR 與 SSIM 都比 COMBO 強，texture 特徵家族明顯改善。表示 R39 形狀 prior 帶了一些超出單純形狀範圍的有用容量。

但 a030 沒解掉 R40 問題。Lines / grid 在 a030 之後仍然弱：high-frequency retention 只從 `0.0506` 上升到 `0.0913`。Mixed fields 也仍然細節不足：COMBO 與 a030 大都重建出大結構，但 fine grid / texture 內容掉了。Edge / defect 場景的 pixel 分數在 a030 下變好，但銳利度指標相對 COMBO 掉，所以這些增益要等 R40 訓練後的視覺檢查再下結論。

目前證據支持原本 R40 設計：從 COMBO 與 R39 a030 兩個起點訓練、用受控 microscopy 特徵覆蓋，訓練後再跑既有 ring guard 加 COMBO 權重平均，才考慮升級。

## Baseline 後的改進思考

baseline 證據顯示三種行為：

1. R39 a030 真的多了一些 capacity。它在任何 R40 訓練之前就把 held-out microscopy 驗證集拉得比 COMBO 好，特別是 textures 與 large regions。所以 a030-start 候選有意義。
2. 最難的特徵還是週期細結構。Lines / grid 仍離可接受的細節保留度差很遠；mixed fields 大多只重建出大形狀。R40 不能只用平均 PSNR / SSIM 判斷。
3. 細節保留與穩定 ring 重建可能拉鋸。a030 的某些 pixel 分數增益伴隨 edge-retention 下降，所以每個 endpoint 都需要 ring guard，必要時還要做 COMBO 權重平均。

R40 解讀規則建議：

- `r40_micro_capacity_a030` 當第一個 capacity 探針，不是直接升級候選。
- 要逐家族進步：lines / grid、textures、defects、mixed fields 都要進步；只有 large-region 進步不夠。
- 如果 R40 平均分數進步但代表性圖上 grid 還是被抹掉，記成 data-coverage 失敗。
- 如果 R40 microscopy 細節進步但 ring 退步，先跑 COMBO 權重 sweep，再考慮外部 GMF。
- 如果兩個 R40 endpoint 都還抹 grid，下一輪要超出資料組成的範圍，改試保留細節的目標，而不是再加合成場景。

## 訓練紀錄

兩個預定的 R40 capacity 探針都在 2026-05-04 跑了 100 epochs。

| Candidate | 起點 | 完成的 run |
|---|---|---|
| `r40_micro_capacity_a030` | R39 a030 | `Traing_Progress/training_progress_GESR_v1_v5_ST0p8_SWP_r40_micro_capacity_a030_20260504_134537/` |
| `r40_micro_capacity_combo` | COMBO | `Traing_Progress/training_progress_GESR_v1_v5_ST0p8_SWP_r40_micro_capacity_combo_20260504_145920/` |

訓練後分析時，`best_tradeoff.pth.tar` 與 `latest.pth.tar` 都評估了——trainer 選的最佳 checkpoint 與最後一個 epoch 在 microscopy 特徵 trade-off 上最佳化的點不同。

## 訓練後的 microscopy 驗證

下面所有 row 都用 held-out `micro_val_unseen`。

| Model | Avg PSNR | Avg SSIM | High-frequency retention | Edge retention | Contrast retention |
|---|---:|---:|---:|---:|---:|
| COMBO baseline | `22.7326` | `0.8588` | `0.2234` | `0.6607` | `0.8857` |
| R39 a030 baseline | `25.0323` | `0.8904` | `0.2206` | `0.6181` | `0.9252` |
| `r40_micro_capacity_a030` best | `29.6323` | `0.9573` | `0.7904` | `0.9880` | `1.0132` |
| `r40_micro_capacity_combo` best | `28.9546` | `0.9506` | `0.8485` | `1.0336` | `1.0281` |
| `r40_micro_capacity_a030` latest | `31.2633` | `0.9659` | `0.6791` | `0.9338` | `0.9737` |
| `r40_micro_capacity_combo` latest | `31.1998` | `0.9651` | `0.7422` | `0.8923` | `0.9654` |

microscopy 特徵 capacity 大幅提升。best checkpoint 保留的高頻內容遠多於 COMBO 與 R39 a030，latest checkpoint 拿到最高的 pixel-level 分數。這驗證 R40 的核心假說：之前在 grid、texture、defect 上的失敗主要是訓練分布覆蓋不足，不是模型本體能力上限。

## 端點 local ring guard

訓練的 endpoint 不能直接升級。每個 endpoint checkpoint 在 local 三尺度 ring 穩定度上都比 COMBO 退步。

| Candidate checkpoint | 8px local step std | 0.8px local step std | 0.08px local step std | Verdict |
|---|---:|---:|---:|---|
| COMBO reference | `0.1389` | `0.1509` | `0.1185` | baseline |
| `r40_micro_capacity_a030` best | `0.2936` | `0.1915` | `0.1596` | capacity-only |
| `r40_micro_capacity_combo` best | `0.1945` | `0.1585` | `0.1549` | capacity-only |
| `r40_micro_capacity_a030` latest | `6.0583` | `0.3739` | `0.2665` | capacity-only |
| `r40_micro_capacity_combo` latest | `0.2679` | `0.2932` | `0.1919` | capacity-only |

最佳的直接 endpoint 是 `r40_micro_capacity_combo` best，但即使是它，8px 與 0.08px ring 行為的損害還是大到不能直接升級。

## COMBO 權重平均 sweep

因為 endpoint 改善了 microscopy 特徵但傷了 ring，所以照原計畫跑 COMBO ↔ R40 權重 sweep，interpolation 的 R40 端用 `r40_micro_capacity_combo` best。

| Alpha | Avg PSNR | High-frequency retention | Edge retention | 8px ring | 0.8px ring | 0.08px ring | Verdict |
|---:|---:|---:|---:|---:|---:|---:|---|
| 0.35 | `25.9248` | `0.2706` | `0.7123` | `0.1508` | `0.1387` | `0.1197` | safe but modest capacity |
| 0.40 | `26.4316` | `0.3020` | `0.7271` | `0.1580` | `0.1412` | `0.1214` | 8px local fail |
| **0.45** | **`26.8911`** | **`0.3414`** | **`0.7458`** | **`0.1510`** | **`0.1379`** | **`0.1199`** | **best local guarded trade-off** |
| 0.47 | `27.0612` | `0.3587` | `0.7536` | `0.1616` | `0.1314` | `0.1324` | 8px local fail |
| 0.50 | `27.2972` | `0.3859` | `0.7664` | `0.1651` | `0.1441` | `0.1263` | 8px local fail |

可用區間很窄。Alpha `0.45` 是目前最佳 local trade-off：在 held-out microscopy 特徵上明顯比 COMBO 與 R39 a030 強，且三個 local ring 尺度都壓在 sweep 用的 local guard 門檻底下。Alpha `0.47` 與 `0.50` 拿到更多 microscopy 細節，但 8px local guard 已經沒過。

Guarded checkpoint：

`Experiments/R40_MicroscopyFeatureCoverage/results/weight_sweep/combo_best_low_alpha/checkpoints/a045/best_tradeoff.pth.tar`

## 代表性視覺檢查

guarded 權重平均候選的代表性對比：

`Experiments/R40_MicroscopyFeatureCoverage/results/weight_sweep/combo_best_low_alpha/r40_a045_micro_comparison_sheet.png`

視覺檢查與指標方向一致：

- Lines / grid：R40 a045 比 COMBO 與 R39 a030 多回復了不少週期 line 結構，但仍比乾淨 label 軟。
- Textures：R40 a045 把重複紋理場保得比 baseline 好很多。
- Defects：R40 a045 保住邊緣缺角與小亮 / 暗 defect mark，沒讓大區域塌掉。
- Mixed fields：R40 a045 把大形狀與部分 fine 結構推進去，但背景 grid 仍比 label 弱。這是 R40 主要還沒解的弱項。

## 外部 GMF 狀態

`r40_combo_best_avg_a045` 用三個提供的 `GMF_score.txt` 跑完外部 GMF，放在：

`Experiments/R40_MicroscopyFeatureCoverage/results/external_gmf/`

方法：對連續 PosY 算 raw step_std，只移除 `|z| > 5` 的 GMF 失敗 step。三個尺度都沒移除任何 step。

| scale | R40 a045 外部 step_std | COMBO 外部 step_std | delta % | status |
|---|---:|---:|---:|:---:|
| 8px | `0.189750` | `0.154515` | **+22.80%** | REGRESSED |
| 0.8px | `0.133314` | `0.131560` | +1.33% | TRADEOFF_OK |
| 0.08px | `0.097048` | `0.099891` | **−2.85%** | IMPROVED |

逐 step 的 audit 檔放在：

`Experiments/R40_MicroscopyFeatureCoverage/results/external_gmf/step_audit/`

外部 verdict 是 **RESEARCH_CAPACITY_ONLY**。R40 不更新正式 baseline 也不進 approved alternates。

## 目前 verdict

R40 作為 capacity 實驗成功。當合成 microscopy 風格的 grid、紋理、大塊區域、defect 進到訓練分布裡，模型可以把它們重建得比之前清楚很多。

R40 訓練 endpoint 是研究用，因為它們傷 ring 穩定度。`r40_combo_best_avg_a045` 是有意義的 local guarded 候選：過了 local 三尺度 ring guard，且在 held-out microscopy 特徵上比 COMBO 與 R39 a030 都強。但外部 GMF 顯示 local 安全沒轉到 8px 外部 guard。

R40 不升級。正式 baseline 仍是 COMBO。發現本身仍重要：資料覆蓋可以教模型把 microscopy 特徵重建得更清楚，但保留策略還不夠溫和、保不住既有的 8px 外部 ring 能力。

下一步建議：

1. R41 圍繞較溫和的保留策略設計：保住 R40 microscopy 特徵覆蓋，但用更低 learning rate、較短 fine-tune、更強 ring replay、或顯式的細節保留目標，把 endpoint 對 COMBO 的 drift 壓下來。
2. 把 R40 特徵 taxonomy 與驗證集留作 capacity benchmark。
3. R40 不升級也不當 approved alternate。

## 跨資料集補測 — R40 a045 在 R39 shape_val_unseen 上的表現（2026-05-10）

回頭把 R40 a045 拉到 R39 shape_val_unseen（純幾何形狀 7 類、210 對）跑了一次 inference，補上 R40 a045 在 R40 micro_val_unseen 之外的對照數字。新重建放在 `Experiments/R39_ShapeGeneralization/results/a030_microscopy_eval/r40_a045_on_shape/`，timestamp `20260504_174058`。

R39 shape_val_unseen 整體（7 類平均）：

| 指標 | COMBO | R39 a030 | R40 a045 |
|---|---:|---:|---:|
| PSNR | `22.8411` | `25.0326` | `26.9147` |
| SSIM | `0.9078` | `0.9461` | `0.9633` |
| HF retention | `0.3021` | `0.4598` | `0.5083` |
| Edge retention | `0.7913` | `0.8797` | `0.9925` |
| Contrast retention | `0.8118` | `0.8864` | `0.9643` |
| 邊界 F1 | `0.8230` | `0.8752` | `0.9009` |
| 形狀錯誤 | `0.3386` | `0.2718` | `0.2526` |

七類純幾何形狀全部 R40 a045 比 a030 高 PSNR；對 COMBO 平均 PSNR 差距 R40 a045 `+4.07 dB`（a030 是 `+2.19 dB`）。

跨資料集 R40 a045 整體 PSNR 落差：R40 micro_val_unseen `26.8911`、R39 shape_val_unseen `26.9147`，差 `−0.0236 dB`。

也就是說 R40 訓練資料雖然加了顯微特徵覆蓋，模型在純幾何形狀上不僅沒退，還比 a030 更強。R40 a045 不是「換顯微強度但失形狀」的取捨，是所有靜態指標（PSNR、SSIM、HF retention、Edge retention、邊界 F1、形狀錯誤、Contrast retention）對 COMBO 跟 a030 都贏，代價只在外部 8 px 連續位移穩定性（既有結果 `+22.80%`）。

完整三方對比（COMBO vs a030 vs R40 a045），含逐 stage 數字、邊界 F1、形狀錯誤、跨資料集對照、視覺對比，見 [`R39_A030_MICROSCOPY_EVALUATION.md`](../../R39_ShapeGeneralization/reports/R39_A030_MICROSCOPY_EVALUATION.md)。

本節為觀察記錄，不改 R40 升級判定（外部 8 px 仍超過 3% 升級上限與 7% 替代容忍區，R40 a045 維持 `RESEARCH_CAPACITY_ONLY`）。

## α 補密 sweep（2026-05-11）

α=0.45 是 R40 sweep 找到的「最佳本地守門」點，外部 8 px 卻退步 `+22.80%`，超過 3% 升級上限與 7% 替代容忍區。補密 sweep `0.42` / `0.43` / `0.44` 三個點，看 α 略低能不能在本地守門過的前提下，把外部 8 px 退步幅度降到容忍區內。

補密 sweep 結果（`run_r40_weight_sweep.py` 同管線、`cuda:0`）：

| α | micro PSNR | HF retention | Edge retention | ring 8 px | ring 0.8 px | ring 0.08 px | 本地守門 |
|---:|---:|---:|---:|---:|---:|---:|---|
| 0.40（既有） | `26.4316` | `0.3020` | `0.7271` | `0.1580` | `0.1412` | `0.1214` | 8 px 不過 |
| **0.42（新）** | `26.6228` | `0.3172` | `0.7343` | `0.1524` | `0.1448` | `0.1337` | 三尺度過（8 px 邊緣、0.08 px 接近 `0.135` 上限） |
| **0.43（新）** | `26.7150` | `0.3250` | `0.7386` | `0.1495` | `0.1448` | `0.1255` | 三尺度過 |
| **0.44（新）** | `26.8039` | `0.3332` | `0.7417` | `0.1630` | `0.1411` | `0.1240` | 8 px 不過（且高於 α=0.45） |
| 0.45（既有） | `26.8911` | `0.3414` | `0.7458` | `0.1510` | `0.1379` | `0.1199` | 三尺度過（外部 8 px `+22.80%` 已知） |

本地守門上限：8 px ≤ `0.155`、0.8 px ≤ `0.155`、0.08 px ≤ `0.135`。

觀察：

- α=0.43 是補密 sweep 中最穩的點：本地 8 px `0.1495` 比 α=0.45 的 `0.1510` 略低，本地三尺度都過守門，micro PSNR `26.72` 介於 α=0.40 跟 α=0.45 之間。
- α=0.42 本地三尺度也都過，但 0.08 px `0.1337` 接近 `0.135` 上限，邊緣狀態。
- α=0.44 本地 8 px `0.1630` 反而高於 α=0.45 的 `0.1510`，這個方向不單調——是權重平均插值在 sweet spot 附近的微觀震盪，不能假設 α 0.40-0.45 之間 8 px 是線性下降。
- 顯微能力跟 α 大致單調（α 越高顯微越強），但 ring 守門非單調。

從 α=0.45 的 local → external 倍率（`0.1510 → 0.1898` = ×1.257）線性外推：

- α=0.43 外推外部 8 px ≈ `0.188`（vs COMBO `0.1545`，外推退步 `+21.6%`）
- α=0.42 外推外部 8 px ≈ `0.192`（外推退步 `+24.2%`）

兩個外推都仍超出 7% 替代容忍區（`0.1653`）跟 3% 升級上限（`0.1591`）。外推為線性假設，實際數字以外部 GMF 量測為準。

補密 sweep 產物：

- checkpoints：`results/weight_sweep/combo_best_low_alpha/checkpoints/a042/`、`a043/`、`a044/`（各 `best_tradeoff.pth.tar`）
- micro 重建：`results/weight_sweep/combo_best_low_alpha/micro_recon/a042/`、`a043/`、`a044/`
- 本地 ring 守門摘要：`results/weight_sweep/combo_best_low_alpha/ring_guard/a042_ring_guard_summary.json`（其他 α 同名替換）
- sweep 總表更新：`results/weight_sweep/combo_best_low_alpha/sweep_summary.json` / `sweep_summary.md`

### α=0.42 / α=0.43 外部 GMF 補測實際結果（2026-05-11）

α=0.42 跟 α=0.43 的外部三尺度 ring 重建在 2026-05-11 跑完（重建 BMP 位置 `results/external_gmf_a042/reconstruct_progress_*/` 跟 `external_gmf_a043/reconstruct_progress_*/`，sweep tool 也在 `weight_sweep/combo_best_low_alpha/ring_recon/a042/` 跟 `a043/` 各放了等價副本）。外部 GMF 視覺定位工具產生 `GMF_score.txt`，`r40_external_compare.py` 解析後實際 step_std：

| 候選 | 8 px | Δ vs COMBO | 0.8 px | Δ vs COMBO | 0.08 px | Δ vs COMBO | verdict（3% 升級上限） |
|---|---:|---:|---:|---:|---:|---:|---|
| COMBO 基準 | `0.154515` | — | `0.131560` | — | `0.099891` | — | — |
| α=0.42 | `0.127574` | **−17.44%** | `0.141836` | +7.81% | `0.111166` | +11.29% | `RESEARCH_CAPACITY_ONLY` |
| α=0.43 | `0.145379` | **−5.91%** | `0.127411` | **−3.15%** | `0.121382` | +21.52% | `RESEARCH_CAPACITY_ONLY` |
| α=0.45（既有） | `0.189750` | +22.80% | `0.133314` | +1.33% | `0.097048` | −2.85% | `RESEARCH_CAPACITY_ONLY` |

實際數字遠比線性外推（×1.257）預測的好——α 微調 sweep 不是線性逼近最佳點，三個 α 點落在三種不同的 trade-off pattern。

#### 觀察

- **α=0.42 的 8 px 大幅改善（−17.44%）**，但 0.8 px 跟 0.08 px 都退步（+7.81% / +11.29%）。
- **α=0.43 在 8 px 跟 0.8 px 兩個尺度都比 COMBO 好**（−5.91% / −3.15%），但 0.08 px 退 `+21.52%`。
- **α=0.45 是相反 pattern**：8 px 退 +22.80% 但 0.08 px 改善 −2.85%、0.8 px 幾乎持平。
- 三個 α 點各落在不同的 trade-off pattern——α 微調的方向不是「8 px 線性下降」這麼單純，是「換 8 px 跟 0.08 px 退步的不同組合」。
- 兩個新 α 都仍不過 3% 升級上限。用 7% 替代容忍區判定（以 R38v2 對 COMBO 最差的 +6.6% 為錨）：α=0.43 在 8 px / 0.8 px 兩尺度過，但 0.08 px `+21.52%` 仍遠超容忍區；α=0.42 三尺度都有過跟不過的指標。

#### 跟 R39 a030 比較

| 候選 | 8 px Δ | 0.8 px Δ | 0.08 px Δ |
|---|---:|---:|---:|
| R39 a030 | −6.94% | +6.42% | −15.97% |
| R40 α=0.43 | −5.91% | −3.15% | +21.52% |

兩者 8 px 改善幅度接近（−6% 上下），但小尺度 pattern 相反：a030 是 `0.08 px 改善 / 0.8 px 退步`、α=0.43 是 `0.8 px 改善 / 0.08 px 退步`。兩者落在不同的 trade-off 子空間。

#### 顯微能力 vs 外部 GMF 整合

| 候選 | micro PSNR | HF retention | 外部 8 px Δ | 外部 0.8 px Δ | 外部 0.08 px Δ |
|---|---:|---:|---:|---:|---:|
| COMBO | `22.7326` | `0.2234` | — | — | — |
| α=0.42 | `26.6228` | `0.3172` | **−17.44%** | +7.81% | +11.29% |
| α=0.43 | `26.7150` | `0.3250` | **−5.91%** | **−3.15%** | +21.52% |
| α=0.45 | `26.8911` | `0.3414` | +22.80% | +1.33% | −2.85% |

α=0.42 / α=0.43 顯微能力略低於 α=0.45（PSNR 26.62 / 26.72 vs 26.89），但仍遠勝 COMBO；同時 8 px 大幅改善。代價在小尺度（0.08 px）。

#### 產物

- `results/external_gmf_a042/external_compare_summary.json`
- `results/external_gmf_a043/external_compare_summary.json`
- `reports/R40_EXTERNAL_COMPARE_a042.md`
- `reports/R40_EXTERNAL_COMPARE_a043.md`

本節為觀察記錄，不改 R40 升級判定。三個 α 點都不通過 3% 升級上限與 7% 替代容忍區（α=0.42 跟 α=0.43 卡 0.08 px、α=0.45 卡 8 px），維持 `RESEARCH_CAPACITY_ONLY` 標籤。但 α 補密 sweep 揭露了一個之前沒看到的事實：R40 weight averaging 在不同 α 點落到「不同尺度退步」的 trade-off pattern，不是線性 8 px 改善。

## 跨輪互補權重平均 — R40 a043 × R39 a030（2026-05-11）

α=0.43 的 trade-off pattern（8 px / 0.8 px 改善、0.08 px 退步）跟 R39 a030（8 px / 0.08 px 改善、0.8 px 退步）方向互補。兩者做 5 點權重平均 sweep（α=0 是純 a030、α=1 是純 a043，中間 0.25 / 0.50 / 0.75 補測）：

| α | 8 px Δ | 0.8 px Δ | 0.08 px Δ | verdict |
|---:|---:|---:|---:|---|
| 0.0（a030） | `−6.94%` | `+6.42%` | `−15.97%` | `PASS_TRADEOFF` |
| **0.25** | **`−5.18%`** | **`+1.51%`** | **`+0.51%`** | **`PASS_UPGRADE_GUARD`** |
| 0.50 | `−2.01%` | `+13.42%` | `−6.73%` | `RESEARCH_CAPACITY_ONLY` |
| 0.75 | `−6.62%` | `+15.61%` | `+11.59%` | `RESEARCH_CAPACITY_ONLY` |
| 1.0（a043） | `−5.91%` | `−3.15%` | `+21.52%` | `RESEARCH_CAPACITY_ONLY` |

α=0.25 候選（`r39r40_complementary_avg_a025`）三尺度都在 3% 升級上限內，是專案歷史上首個跨三尺度都過 3% 上限的候選。R40 a043 本身在 trade-off 曲線的另一端（α=1），不在這個過 3% 上限的點上，但提供了 sweep 的另一端錨。

中間 α=0.50 / 0.75 出現非線性的 0.8 px 凸起（+13% / +15%，兩端都在 ±7% 內），跟線性外推預測不符——這跟 R40 α 補密 sweep（0.42 / 0.43 / 0.44）的非線性觀察一致。

完整 5 點 trade-off 數字、checkpoint 路徑、解析報告見 [`R39R40_COMPLEMENTARY_AVG_RESULTS.md`](../../R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_COMPLEMENTARY_AVG_RESULTS.md)。

`r39r40_complementary_avg_a025` 於 **2026-05-11 升級為 approved alternate**（balanced full-spectrum slot），詳見 `ESTIMATOR_POLICY.json` 的 `approved_alternates`；完整能力評估見 [`R39R40_AVG_a025_CAPABILITY_EVAL.md`](../../R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_AVG_a025_CAPABILITY_EVAL.md)。R40 a043 本身仍是 sweep 端點，未獨立升級，但作為 a025 的關鍵原料保留。

本節為觀察記錄，不改 R40 a045 / a042 / a043 / a044 既有 `RESEARCH_CAPACITY_ONLY` 狀態。a043 雖然作為 a025 sweep 端點貢獻升級，獨立部署的 verdict 仍為 RESEARCH_CAPACITY_ONLY（0.08 px +21.52% 太大）。
