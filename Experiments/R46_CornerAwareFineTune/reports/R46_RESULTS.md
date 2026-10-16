# R46 結果 — a025 邊角細節微調(路徑 B)

狀態:**訓練 + 主要評估完成;ring guard 三尺度全部 FAIL。判定 RESEARCH_ONLY,不升級。**

## 摘要

R46 是以 a025 為起點、用低學習率(4e-6)強化既有邊緣銳度 / 高頻保留權重的 15 epoch 微調。**結果是一個經典的 trade-off failure**:主場(R39 / R40 顯微 / 形狀指標)大幅進步,但 ring 守門全面崩潰。

- **整體影像品質 PSNR vs a025:R39 shape val +3.46 dB,R40 micro val +2.14 dB**(配對 t 檢定 p < 10⁻⁷⁰)
- **所有指標在可解析尺度(supra-Rayleigh)跟混合區都顯著贏 a025**:角點保留 +5.0/+11.8 個百分點,直邊覆蓋 +9.2/+10.5,邊界 F1 +6.6/+10.3,HF 保留 +29.6/+28.5
- **但本地三尺度 ring guard 全部 FAIL**(odd 模式,跟 a025 / COMBO baseline 對齊):
  - 8 px:R46 internal step_std 0.7492 vs COMBO 0.1389,**退步 +439%**
  - 0.8 px:R46 0.2906 vs COMBO 0.1509,**退步 +93%**
  - 0.08 px:R46 0.2098 vs COMBO 0.1185,**退步 +77%**
- **唯一明顯退步的 stage 是 R40 stage_29 細線網格**(PSNR -2.20 dB),這個訊號當時就提示「次解析尺度過銳化」副作用——ring guard 結果證實這個副作用比想像中嚴重得多

**判定**:**RESEARCH_ONLY,不升級**。R46 證明 path B 既有 hyperparam 強化能大幅推 a025 在 R39 / R40 主場,但代價是 ring 能力崩潰。下一步若要保留 R46 的 R39 / R40 增益、又守 ring,要重新設計訓練資料配比或 loss 條件化,但目前的 R46 v1 不可作為 approved alternate。

**關鍵教訓**:強化 edge / HF weight 同時提高了「次解析尺度結構的假高頻」,環形 PSF 解卷積依賴的低頻穩態被破壞了。**R44 系列「沒有單一現成候選同時保住所有結構」的結論在 R46 路徑 B 上再次被驗證**。

## 設計回顧

詳見 [README.md](../README.md)。

| 設定 | 值 |
|---|---|
| 起點 checkpoint | a025 best_tradeoff(`Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/checkpoints/a025/best_tradeoff.pth.tar`) |
| 訓練資料 | `r40_micro_capacity_train`(1300 對:550 環形 + 350 R39 形狀 + 400 R40 顯微) |
| 學習率 | 4.0e-6 |
| 訓練輪數 | 15 epoch |
| `W_GRADMAG` | 0.8 → 1.0 |
| `W_EDGE_ORI_SIMPLE` | 0.3 → 0.4 |
| `W_HF_LAP` | 0.15 → 0.20 |
| `W_EDGELOCAL_LAP_END` | 0.06 → 0.08(ramp E1/E2 從 6/20 縮到 2/10) |
| `BEST_EPOCH_MIN` | 預設 20 → 5(微調短輪數需要) |
| `BOUNDARY_GEOM` / `MOTION` / `SEQ` / `KD` | 全關 |

## 訓練紀錄

| Epoch | Total | Rec | Edge | PSNR | SSIM | 註 |
|---:|---:|---:|---:|---:|---:|---|
| 0(baseline = a025 在 R40 train val split) | 0.1186 | 0.0081 | 0.0768 | 24.04 | 0.8782 | 起點 |
| 2 | 0.1083 | 0.0070 | 0.0715 | 25.22 | 0.8911 | |
| 4 | 0.1025 | 0.0063 | 0.0676 | 25.82 | 0.9001 | |
| 6 | 0.0993 | 0.0060 | 0.0655 | 26.05 | 0.9049 | |
| 8 | 0.0972 | 0.0059 | 0.0647 | 26.14 | 0.9073 | |
| 10 | 0.0961 | 0.0057 | 0.0639 | 26.27 | 0.9093 | |
| 12 | 0.0950 | 0.0056 | 0.0633 | 26.33 | 0.9108 | |
| 14 | 0.0937 | 0.0056 | 0.0627 | 26.39 | 0.9119 | |
| **Best** | — | — | — | — | — | **epoch 9**(tradeoff −0.0031) |

訓練輸出：完整 run 依 `../ARCHIVE_POINTER_20260824.md` 從 H 槽恢復；D 槽代表模型在 `../results/archive_retained_20260824/training_checkpoints/`。

Best checkpoint:`.../weights/best_tradeoff.pth.tar`

## R39 shape_val_unseen 整體(7 類平均,210 對)

| 指標 | COMBO | a030 | a043 | a025 | **R46** | Δ R46 - a025 |
|---|---:|---:|---:|---:|---:|---:|
| PSNR | 22.84 | 25.03 | 26.75 | 25.51 | **28.97** | **+3.46 dB** |
| SSIM | 0.9078 | 0.9461 | 0.9621 | 0.9512 | **0.9733** | +0.022 |
| HF retention | 0.3021 | 0.4598 | 0.5007 | 0.4740 | **0.6710** | +0.197 |
| Edge retention | 0.7913 | 0.8797 | 0.9849 | 0.9087 | **1.2091** | +0.300 |
| Contrast retention | 0.8118 | 0.8864 | 0.9592 | 0.9072 | **1.0645** | +0.157 |
| 邊界 F1 | 0.8230 | 0.8752 | 0.8982 | 0.8816 | **0.9347** | +0.053 |
| 形狀錯誤(↓) | 0.3386 | 0.2718 | 0.2557 | 0.2683 | **0.2244** | −0.044 |
| 角點保留 | — | — | — | — | **0.6823** | (新加) |
| 直邊覆蓋 | — | — | — | — | **0.8769** | (新加) |

(COMBO / a030 / a043 / a025 數字取自 a025 capability eval 報告)

## R40 micro_val_unseen 整體(5 類平均,100 對)

| 指標 | COMBO | a030 | a043 | a025 | **R46** | Δ R46 - a025 |
|---|---:|---:|---:|---:|---:|---:|
| PSNR | 22.73 | 25.03 | 26.72 | 25.41 | **27.55** | **+2.14 dB** |
| SSIM | 0.8588 | 0.8904 | 0.9176 | 0.8968 | **0.9380** | +0.041 |
| HF retention | 0.2234 | 0.2206 | 0.3250 | 0.2428 | **0.7096** | +0.467 |
| Edge retention | 0.6607 | 0.6181 | 0.7386 | 0.6434 | **0.9531** | +0.310 |
| Contrast retention | 0.8857 | 0.9252 | 0.9534 | 0.9348 | **1.0236** | +0.089 |
| 邊界 F1 | 0.4914 | 0.5454 | 0.6103 | 0.5635 | **0.6699** | +0.106 |
| 形狀錯誤(↓) | 0.7489 | 0.7020 | 0.6845 | 0.6989 | **0.6468** | −0.052 |
| 角點保留 | — | — | — | — | **0.6067** | (新加) |
| 直邊覆蓋 | — | — | — | — | **0.6967** | (新加) |

## 逐 stage PSNR vs a025

| Stage | a025 | **R46** | Δ |
|---|---:|---:|---:|
| stage_01_triangles | 24.69 | 28.26 | **+3.57 dB** |
| stage_02_circles | 26.55 | 30.65 | **+4.10 dB** |
| stage_03_rectangles | 24.15 | 27.29 | +3.14 dB |
| stage_04_ellipses | 27.83 | 31.66 | +3.83 dB |
| stage_05_polygons | 25.88 | 30.01 | **+4.13 dB** |
| stage_06_mixed_simple | 25.78 | 28.65 | +2.87 dB |
| stage_07_mixed_complex | 23.73 | 26.30 | +2.57 dB |
| stage_29_micro_lines_grid | 22.74 | **20.54** | **−2.20 dB ⚠️** |
| stage_30_micro_large_regions | 25.32 | 28.85 | +3.53 dB |
| stage_31_micro_textures | 25.42 | 33.21 | **+7.79 dB** |
| stage_32_micro_edge_defects | 26.79 | 29.88 | +3.09 dB |
| stage_33_micro_mixed_fields | 23.99 | 25.27 | +1.28 dB |

**11 / 12 stage 都顯著贏,唯一 stage_29 退步**——這個 stage 是 R40 細線網格,寬度約 4 像素,絕大部分結構落在次解析尺度(< Rayleigh 11.7 px)。R46 的強化 edge weight 在次解析尺度上產生「假高頻」,反而傷整體 PSNR。**這是物理上限附近過銳化反噬的直接證據**,跟前三輪 Rayleigh 診斷的方法論預期一致。

## Rayleigh 分桶結果

| 指標 | supra(238 張) | mixed(53 張) | sub(19 張) |
|---|---:|---:|---:|
| R46 vs a025 PSNR | **+3.29 dB ***** | **+2.58 dB ***** | +1.15 dB * |
| R46 vs a025 SSIM | +0.018 *** | +0.055 *** | +0.084 ** |
| R46 vs a025 邊界 F1 | +0.066 *** | +0.103 *** | +0.035 n.s. |
| R46 vs a025 角點保留 | +0.050 *** | +0.118 ** | −0.003 n.s. |
| R46 vs a025 直邊覆蓋 | +0.092 *** | +0.105 *** | −0.017 n.s. |
| R46 vs a025 HF 保留 | +0.296 *** | +0.285 *** | +0.129 *** |
| R46 vs a025 Edge 保留 | +0.312 *** | +0.301 *** | +0.204 *** |
| R46 vs a025 形狀錯誤(↓) | −0.046 *** | −0.056 *** | −0.026 n.s. |

(*** = p < 0.001,** = p < 0.01,* = p < 0.05,n.s. = p ≥ 0.05)

**觀察**:

- **supra-Rayleigh(77% 樣本)**:R46 全面顯著贏,跟設計目標完美對齊
- **mixed(17%)**:R46 全面顯著贏,跟 supra 量級接近
- **sub-Rayleigh(6%)**:PSNR / SSIM / HF / Edge 保留仍顯著贏(訊號被物理壓得較小但有改善),但角點 / 直邊 / 邊界 F1 / 形狀錯誤都 n.s.——次解析尺度結構級指標飽和,符合物理上限預期

## R46 vs a025 配對 t 檢定(整體 310 張)

| 指標 | n | mean delta | t | p-value |
|---|---:|---:|---:|---:|
| PSNR | 310 | +3.04 dB | 23.51 | < 10⁻⁷⁰ |
| SSIM | 310 | +0.028 | 11.18 | < 10⁻²⁴ |
| 邊界 F1 | 310 | +0.070 | 11.64 | < 10⁻²⁶ |
| 角點保留 | 287 | +0.058 | 4.60 | < 10⁻⁵ |
| 直邊覆蓋 | 299 | +0.089 | 11.44 | < 10⁻²⁵ |
| HF 保留 | 310 | +0.284 | 12.46 | < 10⁻²⁹ |
| Edge 保留 | 310 | +0.303 | 42.55 | < 10⁻¹³¹ |
| 形狀錯誤(↓) | 310 | −0.047 | −6.84 | < 10⁻¹⁰ |

**全部指標整體配對 t 檢定都極顯著贏**。

## 視覺驗證

六個 zoom case 對比圖位於 `results/visual_verification/zoom/`:

| 檔名 | Stage / Frame | 觀察 |
|---|---|---|
| `zoom_1_textures_a043_big_win.png` | R40 stage_31 / 0084 | R46 PSNR=34.71 vs a025 27.33 = **+7.38 dB**;紋理顆粒視覺上明顯更清楚 |
| `zoom_2_triangle_sub_rayleigh.png` | R39 stage_01 / 0097(sw=6px) | R46 PSNR=23.47 vs a025 24.07 = **−0.60 dB**;次解析尺度小三角形 R46 確實沒救出,反而略退,符合物理預期 |
| `zoom_3_rectangle_right_angles.png` | R39 stage_03 / 0275 | R46 PSNR=32.71 vs a025 29.31 = +3.40 dB;矩形直角視覺上更銳 |
| `zoom_4_ellipse_a043_small_loss.png` | R39 stage_04 / 0381 | R46 vs a025 整體仍贏(略),即使是「已經很容易」的大形狀 |
| `zoom_5_large_region_a043_win.png` | R40 stage_30 / 0083 | R46 大區塊邊界改善明顯 |
| `zoom_6_polygons.png` | R39 stage_05 / 0494 | 多邊形 R46 視覺改善明顯 |

**視覺結論**:

- 「直角變圓」現象:R46 在矩形 stage 比 a025 更銳,但仍非完美 90°——物理 PSF 下限(R ≈ 5 px)仍在那,但 R46 接近這個下限
- 「三角形變一坨」現象:**次解析尺度小三角形 R46 真的救不回**,跟前三輪預測一致
- 紋理 / 大區塊 / 多邊形:R46 在這些可解析尺度的視覺改善都明顯,跟指標方向一致

## Ring guard 結果(2026-05-15 補測完成,odd 模式跟 a025/COMBO baseline 對齊)

對 NTU_ImageDataset 三個 pitch 跑 R46 inference,用 `--select-mode odd`(按時間戳排序後取奇數位置一半 frames,跟 a025 / a043 / COMBO 同抽樣慣例),共 101 / 61 / 41 frames。然後 720-angle 分析算 internal step_std,跟 COMBO internal baseline 對照:

| Pitch | R46 odd step_std (Y) | COMBO baseline | delta vs COMBO | 3% 上限 | 通過 3% 門檻? |
|---|---:|---:|---:|---:|---|
| 1 μm Y_100(8 px scale) | **0.7492** | 0.1389 | **+439%** | 0.143 | **FAIL** |
| 0.1 μm Y_60(0.8 px scale) | **0.2906** | 0.1509 | **+93%** | 0.155 | **FAIL** |
| 0.01 μm Y_40(0.08 px scale) | **0.2098** | 0.1185 | **+77%** | 0.122 | **FAIL** |

**三尺度全部 FAIL**(0 / 3 通過 3% 上限)。

### 方法論補充

第一次跑 ring guard 用 `--select-mode all`(全部 frames),數字是 4.0755 / 0.4222 / 0.2352(退步 +2834% / +180% / +98%)——這個 all-frames 結果跟專案慣例 odd 抽樣不對齊,不可跟 a025 / COMBO baseline 對比,所以重做 odd 版本。詳見 `results/ring_recon/r46_all_frames_DEPRECATED/`。Odd 版本數字大幅改善但結論不變。

### 額外觀察(720-angle 序列分析)

| Pitch | input step_std | output step_std | 去噪改善 |
|---|---:|---:|---:|
| 8 px | 9.8446 | 0.7492 | 92.39% |
| 0.8 px | 2.7964 | 0.2906 | 89.61% |
| 0.08 px | 3.8807 | 0.2098 | 94.59% |

R46 模型本身有強去噪能力(input → output 改善 89~95%),但**絕對 step_std 比 COMBO baseline 高 1.8 ~ 5.4 倍**——問題不在「R46 無法去噪」,而在「R46 沒有 COMBO 那麼穩定」。

### 怎麼解讀

Ring 守門的本質是「能不能用 PSF 解卷積把低對比的環形邊界**穩定地**還原出來」——這需要的是低頻穩定性,而**不是**高頻銳度。R46 強化 W_GRADMAG / W_HF_LAP / W_EDGELOCAL_LAP_END 同時放大了「次解析尺度結構的假高頻」,跟 ring PSF 解卷積依賴的低頻穩態打架。

這個結果完全符合前面 stage_29 細線網格 PSNR -2.20 dB 的訊號——當時就是個訊號告訴我們「次解析尺度過銳化反噬」,只是當時還沒看出來破壞嚴重到把 ring 全部洗掉。

### 外部 GMF(2026-05-18 補測完成)

對 R46 ring 三尺度 odd 重建跑外部 GMF 工具,把 `GMF_score.txt` 跟 COMBO 外部 baseline 比對(R33+ 方法論:raw step_std,只移除 `|z|>5` 的 GMF 失敗 step):

| Pitch | R46 external step_std | COMBO external | delta vs COMBO | Verdict |
|---|---:|---:|---:|---|
| 8 px | **1.661451** | 0.154515 | **+975.27%** | `FAIL_OUTSIDE_7PCT` |
| 0.8 px | **0.193531** | 0.131560 | **+47.10%** | `FAIL_OUTSIDE_7PCT` |
| 0.08 px | **0.163458** | 0.099891 | **+63.64%** | `FAIL_OUTSIDE_7PCT` |

**三尺度全部遠超 7% 容忍區**(8 px 退步幾乎 10 倍)。

### 跟既有 baseline 對比

| 候選 | 8 px Δ | 0.8 px Δ | 0.08 px Δ | 整體 verdict |
|---|---:|---:|---:|---|
| COMBO | 0% | 0% | 0% | formal baseline |
| a025 | −5.18% | +1.51% | +0.51% | `PASS_UPGRADE_GUARD` |
| a043 | −5.91% | −3.15% | +21.52% | `RESEARCH_ONLY`(0.08 px 卡關) |
| a030 | −6.94% | +6.42% | −15.97% | `PASS_TRADEOFF` |
| R40 a045 | +22.80% | +1.33% | −2.85% | `RESEARCH_ONLY`(8 px 卡關) |
| **R46** | **+975%** | **+47%** | **+64%** | **`FAIL_OUTSIDE_7PCT`** |

**R46 三尺度都嚴重退步,在歷次升級候選中是最差的**——特別是 8 px scale 退 +975%(其他失敗候選最多 +22%)。

### Internal vs external 對比

| Pitch | internal odd step_std | external step_std | 一致性 |
|---|---:|---:|---|
| 8 px | 0.7492 | 1.661451 | external 比 internal 多 +122% 退步 |
| 0.8 px | 0.2906 | 0.193531 | external 比 internal 少 +33% 退步 |
| 0.08 px | 0.2098 | 0.163458 | external 比 internal 少 +22% 退步 |

**Internal 跟 external 方向完全一致(都 FAIL)**,沒有 internal-external divergence 反例。本專案歷史上 internal FAIL 後 external 通常也 FAIL 這個經驗律在 R46 再次被驗證。

### 產物

- `results/external_gmf/pitch8px/GMF_score.txt`(user 提供)
- `results/external_gmf/pitch0p8px/GMF_score.txt`(user 提供)
- `results/external_gmf/pitch0p08px/GMF_score.txt`(user 提供)
- `results/external_gmf/external_compare_summary.json`(腳本產出)
- `results/ring_recon/r46/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260514_230359/pitch*_odd/`(odd 重建 BMP,送 GMF 用的來源)

### 產物

- `results/ring_recon/r46/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260514_230359/`(三個 pitch 重建 BMP)
- `results/ring_guard/r46_ring_guard_summary.json`(720-angle 完整分析)
- `results/ring_guard/r46_ring_guard_verdict.json`(門檻判定)
- `results/ring_guard/r46_sequence_analysis/`(cross-dataset 圖跟逐 pitch 分析)

## 升級判定

| 條件 | 目標 | 實際 | 通過? |
|---|---|---|---|
| R40 micro 整體 PSNR vs a025 | ≥ +0.5 dB | **+2.14 dB** | ✅✅ |
| R39 shape 整體 PSNR vs a025 | ≥ +0.3 dB | **+3.46 dB** | ✅✅ |
| 角點保留 vs a025(配對 t 顯著) | p < 0.05 | **p < 10⁻⁵** | ✅✅ |
| 角點保留 vs a025 改善 | ≥ +0.5 個百分點 | **+5.8 個百分點** | ✅✅ |
| 本地 ring guard 8 px(odd) | ≤ 3% 上限(0.143) | **0.7492(+439%)** | ❌ FAIL |
| 本地 ring guard 0.8 px(odd) | ≤ 3% 上限(0.155) | **0.2906(+93%)** | ❌ FAIL |
| 本地 ring guard 0.08 px(odd) | ≤ 3% 上限(0.122) | **0.2098(+77%)** | ❌ FAIL |
| 外部 GMF 8 px | ≤ 7% 容忍上限 | **+975%** | ❌ FAIL |
| 外部 GMF 0.8 px | ≤ 7% 容忍上限 | **+47%** | ❌ FAIL |
| 外部 GMF 0.08 px | ≤ 7% 容忍上限 | **+64%** | ❌ FAIL |

**最終判定**:**RESEARCH_ONLY,不升級**。

主指標 4 / 4 達成,ring guard 0 / 3 通過(本地 + 外部都 FAIL),**綜合判定為 research-only**。Ring guard 是本專案 baseline 升級的硬門檻(從 R30 / R33 / R38v2 / a025 系列以來都是),R46 三尺度外部 GMF 全部 FAIL 且退步幅度極大(+47% 到 +975%,8 px 比歷次升級失敗候選最差紀錄 +22.80% 還差 40 倍),不可作為 approved alternate 部署。

R46 取得的進步留作研究紀錄:**path B 既有 hyperparam 強化能在 R39 / R40 主場拿到 +2 ~ +3.5 dB 的大幅改善,但代價是 ring 能力崩潰**。下一輪若要繼續這個方向,需要新的設計來保住 ring。

## Verdict

(本段為人類解讀,後續補完整版)

R46(path B,既有 hyperparam 強化)的訓練是個**清晰的成功**:把 a025 從整體 PSNR 25 推到接近 29(R39)/ 28(R40),所有可解析尺度結構級指標都顯著改善,跟 a043 比也大幅超越。**這個結果超乎前三輪 Rayleigh 診斷的預期(+0.6 ~ 1.0 dB)**——可能解釋:

1. **a025 是 weight averaging 結果**,從來沒對 R40 train profile 做完整 fine-tune,所以微調 slack 比預期大
2. **強化 W_GRADMAG / W_HF_LAP / W_EDGELOCAL_LAP_END 不是 trivial 設定**——這些 weight 直接驅動邊緣銳度跟高頻保留,跟「a025 邊角細節弱」的問題正面對接
3. **R40 train profile(1300 對含 ring replay)夠豐富**,15 epoch 在低 LR 下能拿到大幅改善,但仍守 ring guard 應有的訓練分布

但**唯一弱項**(stage_29 細線網格 -2.20 dB)提示**強化 edge weight 在次解析尺度會反噬**——這跟前三輪「過銳化會在 sub-Rayleigh 反噬」的方法論預期一致,只是強度沒前面看到的那麼劇烈(配對 t 檢定 sub-Rayleigh 整體仍贏 PSNR +1.15 dB)。

**對 user 原始問題的解答**:

- 「直角變圓」:**R46 在矩形 stage 視覺改善明顯,直角更接近物理 PSF 下限**(曲率半徑約 5 px)——但仍非完美直角,物理上限仍在
- 「三角形變一坨」:**次解析尺度小三角形 R46 救不回**(zoom_2 case PSNR 反而 -0.6 dB)——物理上限,符合預期。但中等尺度三角形(stage_01 整體)R46 仍大贏 a025 +3.57 dB

## 限制

1. **BEST_EPOCH_MIN 從 20 降到 5 是個非標設定**,未來若要走 path A 完整 corner-aware loss,要考慮是否回升
2. **沒做外部 GMF**(local ring guard 跟外部 GMF 仍可能 diverge,R26+ 紀錄已說明)
3. **Stage_29 退步** 是個訊號,提示路徑 B 在「sub-Rayleigh 結構主導 stage」上會有副作用——若要解決,可能需要 path A 的條件式 corner-aware loss(只在 supra-Rayleigh 區域加 weight)
4. **R46 改善幅度比預期大**(+3.04 dB vs 預期 +0.6 ~ 1.0 dB),可能反映 a025 本來有 weight averaging slack,而非 R46 設計特別強;若要驗證,要看 R46 是否能在純 R40 train 而非 R40 micro_capacity_train(含 ring + 形狀 replay)上保持一致改善

## 產物

| 項目 | 路徑 |
|---|---|
| 訓練 launcher | `scripts/launch_r46.py` |
| 訓練 log | `results/training.log` |
| Best checkpoint | `results/archive_retained_20260824/training_checkpoints/training_progress_GESR_v1_v5_ST0p8_SWP_r46_a025_corner_finetune_20260514_230359/best_tradeoff.pth.tar` |
| R39 shape 重建 | `results/shape_recon/r46/` |
| R40 micro 重建 | `results/micro_recon/r46/` |
| Capability eval csv | `results/capability_eval/per_pair_metrics_r46_only.csv`、`per_pair_metrics_combined.csv` |
| Stage 平均 | `results/capability_eval/stage_summary_r46.csv` |
| Rayleigh 診斷 | `results/rayleigh_diagnostic/`(per_pair_with_width.csv、aggregate_by_class.csv、rayleigh_summary.md、scatter plot、plots/、validation/) |
| R46 vs a025 配對檢定 | `results/rayleigh_diagnostic/r46_vs_a025_paired_test.csv` |
| 視覺驗證 zoom | `results/visual_verification/zoom/`(6 張單一 case 大圖) |
| Pipeline wrapper | `scripts/run_r46_pipeline.py` |

## 可重跑

```bash
cd D:/GMM_2_Final
# 訓練
python Experiments/R46_CornerAwareFineTune/scripts/launch_r46.py --num-epoch 15

# 訓練完一鍵跑全套評估
python Experiments/R46_CornerAwareFineTune/scripts/run_r46_pipeline.py
```
