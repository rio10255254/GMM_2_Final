# R46 失敗成因診斷

R46 完整通過主指標(R39 PSNR +3.46 dB、R40 PSNR +2.14 dB,配對 t 檢定 p < 10⁻⁷⁰),但 ring guard 三尺度本地 + 外部 GMF 全部 FAIL,最終判定 `RESEARCH_ONLY`。本檔深入驗證失敗成因,不只滿足於「過銳化反噬」這個含糊解釋。

## 結論先講

R46 失敗有**兩個獨立成因**疊加:

1. **Loss balance 嚴重失衡**(根本原因):W_GRADMAG 1.0 + W_EDGE_ORI_SIMPLE 0.4 + W_HF_LAP 0.20 三個高頻 loss 加總**占訓練 loss 92%+**,Rec 重建 loss 只占 **6-7%**,模型訓練被高頻 loss 完全主導
2. **Ring 樣本在 loss 計算上「相對隱形」**(放大效應):雖然 ring replay 樣本占訓練資料 42%(550/1300 對),但 ring PSF 已經低通,GradMag/EdgeOri 在 ring 樣本上產生的 loss 信號極小;模型自然向「能放大 GradMag/EdgeOri」的 R39 形狀 + R40 顯微樣本傾斜學習

這兩個成因共同造成 R46 變成「能在 R39 / R40 上重建出銳邊,但在 ring 上會硬擠假高頻 + 整體位置不穩」的偏差模型。

## 證據一:Loss 組成分布(從 training.log 直接抽出)

R46 每 epoch 的 `[SIMPLETEST]` 行,各 loss 組件百分比軌跡:

| Epoch | Rec | GradMag | EdgeOri | EqGeom | Total |
|---:|---:|---:|---:|---:|---:|
| 1 | 6.5% | 58.5% | 35.0% | 0.0% | 0.138482 |
| 5 | 6.5% | **62.9%** | 30.6% | 0.0% | 0.112644 |
| 8 | 7.9% | 55.5% | 36.5% | 0.0% | 0.089165 |
| 10 | 7.7% | 54.7% | 37.6% | 0.0% | 0.089673 |
| 15 | 7.7% | 54.5% | 37.7% | 0.1% | 0.088517 |

**整個 15 epoch 訓練,GradMag + EdgeOri 加總都在 90 ~ 95% 之間,Rec 維持 6 ~ 8%**。Rec 是直接驅動「重建出正確 PosY 位置」的訓練信號,被高頻 loss 完全淹沒。

對照原本 a025 訓練(W_GRADMAG=0.8、W_EDGE_ORI_SIMPLE=0.3、W_HF_LAP=0.15),Rec 占比應該在 20-30%——R46 把 Rec 占比壓到 6-8% 是設計上的根本錯誤,不是 hyperparam 微調不慎。

## 證據二:PosY 軌跡對比(a025 vs R46,Pitch 1 μm Y_100)

挑 outlier 附近 10 frames(對應 R46 ring guard 在 8 px 尺度的 step_std=1.66 失敗點):

| Frame | a025 PosY | R46 PosY | R46 − a025 | a025 step | R46 step |
|---:|---:|---:|---:|---:|---:|
| 40 | 1176.30 | 1184.10 | +7.80 | — | — |
| 41 | 1168.26 | 1175.91 | +7.65 | −8.04 | −8.19 |
| 42 | 1160.45 | 1168.04 | +7.59 | −7.81 | −7.87 |
| 43 | 1152.27 | 1159.77 | +7.50 | −8.18 | −8.27 |
| **44** | **1144.30** | **1167.28** | **+22.98** | **−7.97** | **+7.51 ⚠️** |
| **45** | 1136.13 | 1144.04 | +7.91 | −8.17 | **−23.24 ⚠️** |
| 46 | 1127.97 | 1135.81 | +7.84 | −8.16 | −8.23 |
| 47 | 1119.93 | 1127.57 | +7.64 | −8.04 | −8.24 |

**兩個發現**:

### (a)整體 fixed_bias:R46 PosY 系統性比 a025 高 ~7.7 px

除了 frame 44 外,R46 跟 a025 的 PosY 差大致是 +7.6 ~ +7.9 px(constant)。這個 systematic offset 不影響 step_std,但代表 R46 重建讓 GMF 模板匹配「整體位置偏」一個 ring radius 等級的距離——對絕對位置敏感的應用(實儀)是大問題。

720-angle 分析回報的 `Center offset verdict: fixed_bias` 直接對應這個現象。

### (b)Frame 44 戲劇性 spike:R46 PosY 突然往回跳 +7.51

R46 在 frame 44 的 PosY 不是「a025 + 7.6 px offset」這條 trajectory 上,而是直接跳回前一 frame 附近的位置(1159.77 → 1167.28,本來該往下走 -8 px,結果往上跳 +7.51 px)。然後 frame 45 補回 -23.24 px。

**這個 spike 不是 GMF 工具失誤**:GMF 工具對 a025 同 frame 沒問題(穩定下降 -8 px)。差別在 R46 重建出來的 frame 44 影像本身——某種高頻偽影讓 GMF 模板找到「錯位置」匹配。

## 證據三:Step distribution 對比

|  | a025 (8 px) | R46 (8 px) | a025 (0.8 px) | R46 (0.8 px) | a025 (0.08 px) | R46 (0.08 px) |
|---|---:|---:|---:|---:|---:|---:|
| n steps | 99 | 99 | 59 | 59 | 39 | 39 |
| median step | −8.02 | −8.01 | −0.84 | −0.80 | −0.087 | −0.103 |
| raw std | **0.1465** | **2.7351** | 0.1335 | 0.1935 | 0.1004 | 0.1635 |
| filtered std | 0.1465 | 1.6615 | 0.1935 | 0.1935 | 0.1635 | 0.1635 |
| max\|dev\| | 0.43 | **11.45** | 0.31 | 0.47 | 0.24 | 0.44 |
| p95\|dev\| | 0.30 | 0.63 | 0.27 | 0.39 | 0.20 | 0.39 |
| outliers (\|z\|>5) | 0 | **2** | 0 | 0 | 0 | 0 |

**兩種失敗模式區別清楚**:

- **8 px scale**:單點 spike(max dev 11.45)主導 raw std,移除 outlier 後仍 filtered std 1.66(a025 的 11.3 倍)——**spike + 全面 jitter 雙重失敗**
- **0.8 / 0.08 px scale**:0 outlier,p95 dev 比 a025 大 50-100%——**純全面 jitter 失敗**,沒有戲劇性 spike

8 px 的 spike 來源解釋:R46 在某些 frame 重建出干擾模板匹配的高頻偽影,讓 GMF 找錯位置(類似 R46 看到一個「近似 ring 但實際不對」的高頻 pattern)。小尺度(0.8/0.08 px)上沒看到 spike,因為小尺度 step 短(0.8/0.1 px),即使 R46 有些 frame 重建異常,PosY 偏差也不容易越過 z=5 threshold。

## 為什麼 R46 在主指標大幅進步但 ring 失敗

**主指標(PSNR / SSIM / 邊界 F1)的數學定義跟 ring step_std 完全不同**:

| 指標類別 | 數學定義 | 對「假高頻」的敏感度 |
|---|---|---|
| PSNR / SSIM | pixel-wise 像素差 + 結構相似度 | 假高頻只要不偏離 GT 太多,反而能拉高(增加細節對齊) |
| 邊界 F1 / 角點保留 | GT 邊界 vs pred 邊界距離 | 假高頻在邊界附近 → 反而看似「邊界更精準」 |
| HF retention / edge retention | pred / GT 高頻能量比 | 假高頻直接拉高指標(這個指標越高未必越好,有 over-shoot 風險) |
| Ring step_std | 連續 frame 的 PosY 變動 std | 假高頻干擾 GMF 模板匹配,直接讓 PosY 跳 → step_std 爆炸 |

R46 訓練資料(R39 形狀 + R40 顯微)上沒有「ring step_std」這個 loss term,只有 Rec / GradMag / EdgeOri / EqGeom。所以模型被優化的方向是「在 R39 / R40 樣本上產生**更銳邊**」,但這個目標跟 ring 上「不要破壞 PosY 穩態」是隱性衝突的。

換句話說:**R46 的訓練 loss 沒有任何項在 punish「ring 上產生假高頻」**,所以模型自由地在 ring 上產生假高頻來追求 GradMag 最小化。

## 為什麼 ring replay 樣本(占 42%)沒守住 ring

直觀預期:訓練資料 1300 對中,ring replay 占 550 對(42%),理論上 ring 樣本應該在 loss 上有可觀貢獻,守住 ring 能力。

實際上:

| 樣本類別 | 數量 | 對 Rec 的 loss 貢獻 | 對 GradMag/EdgeOri 的 loss 貢獻 |
|---|---:|---|---|
| ring replay | 550(42%) | 中等(ring 邊界亮對比明確) | **低**(ring PSF 已低通,GradMag 信號小) |
| R39 形狀 replay | 350(27%) | 中等 | 高(多邊形邊角產生大 GradMag) |
| R40 顯微 | 400(31%) | 中等 | **極高**(紋理 / 細線產生大 GradMag) |

**Ring 樣本上 GradMag/EdgeOri loss 信號本來就低**(沒有銳邊可放大),所以即使 ring 樣本占資料 42%,在 R46 loss(GradMag + EdgeOri 占 92%+)上的占比可能只 10-15%。

模型訓練被「能放大 GradMag 的樣本」拉著走——也就是 R40 紋理 + R39 多邊形——ring 樣本變成「loss 上的隱形人」。

## 對下一輪設計的具體啟示

成因確認後,**R46 v2 / path A 的修正方向應該是**:

### 選項 A:Loss balance 校正(最輕,工程量 < 1 小時)

R46 v2 配方:

| Hyperparam | R46 v1(失敗) | R46 v2 建議 |
|---|---:|---:|
| W_REC | 1.0 | **1.5**(把 Rec 重要性拉到 ~20%) |
| W_GRADMAG | 1.0 | 0.7(從 0.8 略降,給空間) |
| W_EDGE_ORI_SIMPLE | 0.4 | 0.30(回原值) |
| W_HF_LAP | 0.20 | 0.15(回原值) |
| W_EDGELOCAL_LAP_END | 0.08 | 0.06(回原值) |
| LR | 4e-6 | 4e-6(不動) |

預期效果:Rec 占比從 6-7% 拉到 ~ 20%,GradMag + EdgeOri 從 92% 降到 ~ 70%。模型仍會略推 edge sharpness,但 ring 不會被洗光。

**風險**:R39 / R40 改善可能從 +3 dB 降到 +0.5 ~ 1 dB(預期),回到三輪 Rayleigh 診斷原本估計的「微小銳化」量級。

### 選項 B:Ring loss 顯式守門(中等工程,複製 trainer 加 ring-specific loss)

加一個 ring replay 樣本專用的「PosY consistency loss」:對連續 ring frame 的重建,要求 PosY 軌跡平滑(類似 R44 motion loss 概念但針對 ring)。需要動 trainer(複製到 R46/scripts/r46_trainer.py)。

### 選項 C:Path A 條件式 corner-aware loss(大工程)

只在 supra-Rayleigh 區域加 corner-aware weight,sub-Rayleigh 區域不動。理論上能保住 ring(主要在 sub-Rayleigh 尺度活動)+ 推 R39 / R40 supra 結構。但要動 trainer 加 corner mask 計算邏輯,工程量大。

### 我的傾向

**先做選項 A(loss balance 校正)**,工程量最小,直接針對診斷出的根本原因(Rec 占比過低)。如果 A 跑出來:

- R39 / R40 改善 ≥ +0.5 dB **且** ring guard 三尺度通過 7% 容忍區 → R46 v2 升 approved alternate
- R39 / R40 改善 < +0.5 dB → 確認 path B 天花板,考慮選項 C(path A 條件式 loss)
- 仍 ring 退步 > 7% → 加選項 B 的 ring 顯式 loss

## 限制

1. **沒做 R46 各 epoch 的 ring 評估**,所以不知道 ring 能力是「漸進崩潰」還是「epoch 早期就崩」。Best epoch=9 但沒測 epoch 5/7/9/15 的 ring step_std,無法確認最佳 trade-off epoch 是不是更早。
2. **沒做 frame 44 視覺對比**(看 R46 重建影像跟 a025 在 frame 44 視覺差異)。本檔的 spike 解釋基於 PosY 數字推論,沒有視覺確認 R46 確實重建出「干擾 GMF 模板匹配的假高頻」。
3. **沒有對 W_GRADMAG 做 ablation sweep**:選項 A 的建議值(W_REC=1.5、W_GRADMAG=0.7)是基於診斷推論,沒有實驗驗證單獨變動每個 weight 的效果。

## 產物

| 檔案 | 內容 |
|---|---|
| `results/training.log` | 完整訓練 log(loss 軌跡來源) |
| `results/external_gmf/external_compare_summary.json` | 外部 GMF step 統計 |
| `results/external_gmf/pitch*/GMF_score.txt` | 外部 GMF raw 資料 |
| `Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/external_recon/a025/external_gmf/pitch*/GMF_score.txt` | a025 對應 GMF(對照組) |
| `reports/R46_RESULTS.md` | 訓練 + 評估完整紀錄 |
| 本檔 | 失敗成因深入診斷 |

## 可重跑診斷

```bash
# Loss 軌跡
grep "SIMPLETEST" Experiments/R46_CornerAwareFineTune/results/training.log

# PosY + step 對比
python -c "import sys; sys.path.insert(0, 'Experiments/R40_MicroscopyFeatureCoverage/scripts'); from r40_external_compare import parse_gmf_score; ..."
```
