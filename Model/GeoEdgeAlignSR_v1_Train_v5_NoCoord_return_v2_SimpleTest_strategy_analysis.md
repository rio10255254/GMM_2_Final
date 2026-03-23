# 訓練策略分析 (v5 SimpleTest) / Training Strategy Analysis

分析目標: `Model/GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py`

本文聚焦於這個訓練腳本「刻意設計」的策略，以及你觀察到的現象背後可能的原因:

- Epoch 1-5: 重建結果非常銳利、清晰
- 後續 epoch: 邊緣逐漸變得發散、變厚、變糊

## 1. 這份腳本主要在最佳化什麼 (設計目標)

從檔頭註解可以看出主要目標是:

- 避免非自然的週期性高頻 (checkerboard/whiskers) 造成 MATLAB `dftregistration` 失效。
- 避免用 phase/PSR/mining 類的內部指標去「獎勵」人工高頻尖峰 (會讓內部小指標膨脹)。
- 讓 validation / best-selection 與 MATLAB 風格的 phase 評估設定一致。

所以它的訓練策略**不是**「不惜一切代價把畫面變得最銳利」。它更像是在找一個比較穩的收斂盆地 (basin):

- 有利於配準/對位 (phase/shift 穩定)
- 低偽影 (邊界振鈴少、checkerboard 少)
- 盡量符合物理假設 (可選的 PSF-forward 一致性)
- 同時仍保留監督式重建 loss

## 2. 資料路徑、取樣方式與核心訓練設定

### Dataset

- Dataset class: `PairedGrayFolder`
- 資料夾:
  - `Training_Data/tra_src_ring` (src)
  - `Training_Data/tra_lbl_ring` (lbl)
- I/O: 灰階; `uint16` 會除以 `65535` 正規化，否則除以 `255`。
- 取樣: 以 patch 為單位的隨機裁切 (random crop) `CROP_SIZE=256`，沒有 flip/rotate augmentation。
- Batch: `BATCH_SIZE=4`。

### Optimizer / AMP / EMA

- Optimizer: `Adam`
- Base LR: `LR=2e-5`
- 參數群組 (param groups):
  - 其他參數: LR = `LR`
  - `physics_layer`: 初始以 `PHYSICS_LR_MULT` 縮放 LR
  - `weak_psf`: 初始以 `WEAK_PSF_LR_MULT` 縮放 LR
- 混合精度: 預設 `CFG.use_amp=True`
- Gradient clipping: `clip_grad_norm_=1.0`
- EMA: 啟用 (`EMA_DECAY=0.997`)

重點: 這裡**沒有**傳統意義的 LR scheduler。LR 的變化主要透過:

- rescue 的 LR multiplier
- PSF / weak-PSF schedule 的 LR multiplier

## 3. SimpleTest 模式的 loss: 實際在訓練什麼

在 `SIMPLETEST_MODE=True` 時，訓練 loop 使用一組固定的 loss 項 (程式裡有很多進階項目，但在這個模式下大多因為權重為 0 而不生效)。

在 `train_one_epoch` 裡，總 loss 為:

```text
loss_raw =
  W_REC * L_rec
  + W_GRADMAG * L_gradmag
  + W_EDGE_ORI_SIMPLE * L_edge_ori
  + L_eq_total                      (位移等變的幾何正則; 有 schedule)
  + W_STAT * L_stat
  + W_BAND * L_band                 (每 N 個 batch 計算一次)
  + W_HF_LAP * L_hf_lap
  + W_phys_epoch * L_phys           (warmup 後才開始 ramp)
  + W_edgeLocalLap_epoch * L_edgeLocalLap   (ramp; 只在 edge 區域作用)
  + W_DETAIL_BASE * detail_mult * L_detail  (從 DETAIL_START_EPOCH 開始)
```

### 各 loss 的直覺作用

- `L_rec` (Huber + 少量 SSIM): 強化像素擬合; 通常早期會讓「看起來更清楚」。
- `L_gradmag`: 讓 Sobel gradient magnitude 接近 GT; 有助產生邊緣，但不一定能完全控制「邊緣寬度」。
- `L_edge_ori`: 對齊邊緣方向; 有助幾何穩定，抑制怪異邊緣方向。
- `L_stat` (mean/std match): 對齊全域 mean/std，降低對比或亮度漂移。
- `L_band` (FFT band energy match): 對齊中頻 band 能量，抑制頻譜能量漂移。
- `L_hf_lap` (Laplacian difference): 二階導數匹配項; 可保留細節，但也可能與振鈴/ringing 互動 (當其他約束把解往平滑推時)。
- `L_phys` (PSF forward): 要求「SR 經 PSF 模糊後」能接近輸入 src; 偏物理一致性，不是純感知銳利化。
- `L_edgeLocalLap`: 只在 GT 邊緣附近做 Laplacian 匹配 (edge mask 由 GT 產生); 設計上像是 edge detail rescue。
- `L_detail` (DoG band-pass): 把 pred 的 band-pass 細節拉向 GT (edge-gated); guard 觸發時能做一定程度的回銳/補細節。

## 4. 會隨 epoch 改變訓練行為的關鍵 schedule / stage

### 4.1 位移等變性 (Eq) schedule: 最符合你現象的關鍵

SimpleTest 的 `get_eq_factor(epoch1)`:

- E1-5: `eq_factor = 0.0` (明確 warmup-off)
- E6-20: ramp `0 -> 1`
- E21-40: `1.0`
- E41-100: fade `1.0 -> 0.4`

Eq 也不是每個 batch 都算，而是以機率啟用:

- `EQ_PROB = 0.45`
  - 約 45% 的 batch 會套用 eq loss; 一旦啟用，它是很強的 self-consistency 約束。

SimpleTest 的 eq shift 取樣 (`sample_shifts(mode="eq")`):

- 80% tiny shift: `0.01-0.20 px`
- 20% mid shift: `0.20-0.50 px`
- eq 模式不做整數位移 (`EQ_MAX_INT_SHIFT=0`)

### 4.2 SimpleTest 的 "Eq" 內容是什麼 (關鍵細節)

在 `compute_shift_eq_losses` 裡，`SIMPLETEST_MODE=True` 時做的是**純幾何 (geometry-only) 的 eq**:

- 對輸入 `src` 做 subpixel shift `(dx,dy)`，padding 使用 `zeros`
- 再跑一次模型: `pred_shift = model(shift(src))`
- 比較 `pred_shift` 的梯度強度 (gradient magnitude) 與 base prediction 的梯度強度被 warp 後的差異

形式化 (簡化版; 這裡的 `grad()` 可理解成 Sobel magnitude 一類的梯度強度):

```text
mag_s = |grad(pred_shift)|
mag_b = |grad(pred_base)|
mag_b_warp = shift(mag_b, dx, dy)

L_eq_geom_raw = mean_masked( sqrt((mag_s - mag_b_warp)^2 + eps^2) )
L_eq_total = eq_factor * W_EQ_GEOM * L_eq_geom_raw
```

預設值重點:

- `W_EQ_GEOM = 0.5`
- `eq_factor` 會在 E5 後開始 ramp
- shift 是 subpixel; warp 使用雙線性插值 (bilinear)

### 4.3 Edge-local Laplacian schedule (幾乎跟 Eq 同時啟動)

`get_edgelocal_lap_weight(epoch1)`:

- E1-5: `0`
- E6-20: ramp 到 `W_EDGELOCAL_LAP_END` (預設 `0.06`)
- E20 之後: 固定 `0.06`

所以 E5 之後會同時出現兩個「新力量」:

- EqGeom (self-consistency)
- EdgeLocalLap (edge-gated 的 Laplacian match)

### 4.4 Physics forward (更晚開始)

`get_phys_weight(epoch1)`:

- E1-10: `0`
- E11-30: ramp 到 `W_PHYS_MAX` (預設 `0.05`)
- E30 之後: 固定 `0.05`

### 4.5 Weak PSF block 解凍 (也更晚開始)

`apply_weak_psf_schedule` (預設):

- E1-10: `stage0_freeze` (physics + weak-PSF 都 frozen; `beta_scale = 0`)
- E11-30: `stage1_low` (`beta_scale ~ 0.12`)
- E31-80: `stage2_ramp` (`beta_scale` 由 `0.12 -> 0.28`)
- >E80: `stage3_hold`

即使監督式 loss 看起來穩定，weak-PSF/physics 相關模組在中後期的介入，仍可能改變邊緣型態。

## 5. 為什麼會出現「前 5 epoch 很清楚，之後邊緣越來越發散」(我的判斷)

### 主要原因: EqGeom 在 E6 開始啟動，本質上會壓抑極端銳利

你的現象跟 schedule 的對應非常準:

- E1-5: `eq_factor=0`，模型主要被監督式重建 (`L_rec`, `L_gradmag`, `L_edge_ori`) 驅動，外加一些較弱的 stat/band/laplacian 約束。
- 從 E6 起: EqGeom 開始 ramp，到 E20 變得很強。

EqGeom 的計算方式牽涉到「subpixel shift + bilinear warp」的梯度比較。對很銳利的邊而言，subpixel shift 幾乎不可避免會引入插值效果，導致邊緣在像素格上被攤開 (看起來像被 smear)。

因此模型若要在隨機位移下都降低 EqGeom，一個很常見且容易的方向是:

- 降低對高頻的敏感度
- 讓邊緣的梯度峰值稍微降低、支撐範圍稍微變寬
- 視覺上就會像「邊緣變厚 / 變糊 / 發散」

換句話說，邊緣發散可能是這個複合目標下的理性折衷點:

- 監督式 loss 想逼近 GT 的邊
- EqGeom 想要邊在 subpixel shift 下表現得更一致、更可預期
- 折衷常常就變成「沒有那麼刀口銳利」的邊

### 次要原因: E10 之後有更多約束逐步介入

E10 之後:

- physics-forward loss 在 E11+ 開始 ramp
- weak-PSF block 在 E11+ 解凍
- DoG-based 的 `detail_recovery_loss` 在 E10+ 開始進入 loss (但效果取決於 detail-rescue multiplier 有沒有觸發)

如果 PSF/physics 假設與資料有些許不匹配，即使 pixel loss 繼續下降，也可能把解的邊緣型態推向更平滑。

### 控制系統細節: guard 未必會在你需要時有效降低 Eq 壓力

你確實有 oversmooth/thickening guard，但要注意幾個行為:

- Eq shift 會被 override 成 "tiny only" 的條件，是 `thicken_guard_hold > 0` 或 `last_thicken_trigger=True`。
- `thicken_guard` 是拿 `metric_edge_width` 去對比 `edge_width_ref` (來自 `monitor_ref.json`，通常在 run 一開始建立)。

若 `edge_width_ref` 本身不是「很銳利」的 baseline (例如從 scratch 開始訓練)，後期的邊緣變厚可能沒超過相對門檻，導致 guard 觸發不夠早，Eq 壓力就不會被及時抑制。

另外 `self_band_guard` 的 baseline 取 E1-5 history，確實能觸發 Laplacian rescue，但在 SimpleTest 裡它**不會直接降低 `eq_factor`** (SimpleTest 的 `eq_factor` 主要只乘上 `thicken_guard_mult`)。

## 6. 如何快速驗證 (不改 code)

1. 看每個 epoch 的 console log:
   - `[EQ][SIMPLETEST] factor=... shift_range=...`
   - 若邊緣劣化大致從 E6 (factor 轉為非 0) 開始，通常就是 EqGeom 主導的典型訊號。

2. 看 batch log CSV:
   - `*_batch_log_v5.csv` 會有 `loss_eqgeom`, `eq_factor`, `eq_shift_r_min/max` 等欄位。
   - 把 `loss_eqgeom` 對 `loss_gradmag` / `loss_rec` 畫曲線。
   - 如果 `loss_eqgeom` 變成不可忽略的占比，同時邊緣變不銳利，符合「折衷解」的預期。

3. 看 guard 在 log 裡是否真的有觸發:
   - `[GUARD][THICKEN] trigger ...`
   - `[GUARD][BAND] trigger ...`
   - 如果視覺上越來越厚，但 thickening guard 幾乎不觸發，通常是 baseline/reference 沒對齊「你認為的好狀態」。

4. 對照 monitor 輸出:
   - `Traing_Progress/training_progress_*/monitor_epoch_XXX_v5.bmp`
   - 若視覺退化與 Eq ramp 區間 (E6-20) 高度相關，診斷會更扎實。

## 7. 如果你希望後期也維持 E1-5 那種銳利 (調整方向)

你目前不想改 code; 這裡只是指出「如果要改，我會往哪裡動」:

- 降低 Eq 壓力:
  - 降 `W_EQ_GEOM`
  - 降 `EQ_PROB`
  - 延後 Eq 開始 (`EQ_WARMUP_OFF_E`, `EQ_RAMP_START_E`)
  - 縮小 eq shift range (把 `0.20-0.50 px` 的 mid shift 拿掉，只留 tiny shift)

- 讓 thickening guard 更早/更可靠觸發:
  - 確保 `edge_width_ref` 是用「你認為好的銳利狀態」建立，而不是 random init。
  - 或把厚邊門檻改成參考 E1-5 的 self-band baseline，而非 run-start reference。

- 在可控範圍內提升反向回銳項:
  - 小幅提高 `W_EDGELOCAL_LAP_END` 或 `W_DETAIL_BASE`
  - 但要同步盯 `checkerboard` / `hf_proxy`，避免把偽影又拉回來

- 操作層 workaround:
  - 如果 E3-E5 視覺最佳，其實直接選那個 checkpoint 也合理 (腳本本來就有頻繁存 monitor 與權重)。

---

### 結論 (一句話)

在這個「E1-5 關閉 Eq、E6 開始 ramp Eq」的精確 schedule 下，最站得住腳的解釋是:

> 邊緣變厚/發散的主要原因，是 epoch 5 之後啟動的位移等變幾何正則 (`EqGeom`) 會自然偏好較低的 subpixel 敏感度 (常見實現方式就是較厚/較平滑的邊)。E10 之後 physics/weak-PSF 與 detail 機制的介入，會進一步影響中後期的邊緣型態。

---

## English Companion Summary

### Goal of This Note

This note explains why the `v5 SimpleTest` training script can produce very
sharp reconstructions in early epochs and then gradually drift toward thicker,
blurrier edges later.

Observed behavior:

- Epoch 1-5: reconstructions look very sharp and clean
- Later epochs: edges become thicker, softer, and more diffuse

### Main Interpretation

The most likely reason is the **EqGeom schedule**.

In this script:

- epochs 1-5 keep the equivariance term effectively off
- after epoch 5, the geometry-only shift-equivariance regularizer begins to ramp
- after epoch 10, additional physics-related constraints and weak-PSF schedules
  start to matter more

That combination encourages a solution that is more stable under subpixel
shifts, but often less razor-sharp visually.

### What the Script Is Really Optimizing

The script is not trying to maximize visual sharpness at all costs.
It is trying to find a stable basin that balances:

- registration / phase consistency
- low artifact behavior
- physically plausible reconstruction
- supervised pixel and edge recovery

So if a sharper edge becomes too unstable under the equivariance geometry term,
the optimizer may prefer a slightly thicker edge that is more predictable under
subpixel warps.

### Why Epoch 5 Is the Turning Point

This is the key schedule interaction:

- **E1-E5**
  - equivariance geometry pressure is effectively off
- **E6-E20**
  - equivariance geometry ramps up
- **E11+**
  - physics-forward and weak-PSF schedules start to become more active

That timing matches the reported visual transition very closely.

### Practical Reading of the Loss Design

The dominant parts of the loss in `SimpleTest` are:

- reconstruction
- gradient magnitude matching
- simple edge orientation alignment
- geometry-only shift-equivariant consistency
- statistical and band consistency
- high-frequency Laplacian detail terms
- physics-forward consistency
- edge-local detail rescue terms

The important point is that these terms do **not** all push in the same visual
direction. A term that rewards consistency under subpixel shift can naturally
push against maximum apparent sharpness.

### What Likely Causes the Edge Thickening

The strongest explanation is:

1. the equivariant geometry term starts ramping after epoch 5
2. subpixel warping and interpolation punish overly sharp, unstable edge peaks
3. the model learns a compromise with lower subpixel sensitivity
4. visually, that compromise appears as thicker / smoother edges

Later schedules involving physics and weak-PSF modules may further reinforce
that behavior.

### How To Validate This Hypothesis Without Editing Code

Good checks include:

- inspect console logs for the equivariance factor ramp
- inspect batch logs for `loss_eqgeom` and related terms
- inspect guard triggers such as thickening or band guards
- compare monitor outputs around the epoch-5 to epoch-20 range

If visual degradation correlates strongly with the EqGeom ramp, the diagnosis is
much more convincing.

### If You Want To Preserve Early Sharpness Longer

The most plausible adjustment directions would be:

- lower `W_EQ_GEOM`
- lower `EQ_PROB`
- delay the equivariance schedule
- shrink the equivariant shift range
- make thickening guards trigger earlier or more reliably
- carefully strengthen detail rescue terms without reintroducing artifacts

Even without code changes, another practical workaround is simply selecting an
earlier checkpoint if that checkpoint gives the best trade-off for your actual
downstream use.

### One-Sentence Bottom Line

The sharp-to-thick transition is most plausibly caused by the post-epoch-5
equivariance geometry regularizer, with later physics / weak-PSF schedules
further shaping the mid-to-late training edge profile.
