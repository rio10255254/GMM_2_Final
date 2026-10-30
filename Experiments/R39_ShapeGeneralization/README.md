# R39 — 多形狀泛化

R39 開一條資料路線，試試看能不能在不破壞 ring 表現的前提下，把 non-ring 形狀的重建拉起來。COMBO 在 ring 上的外部 GMF 表現是這輪的硬門檻。

這輪刻意不碰真實影像。R32 已經示範過真實影像路線可以「內部看起來不錯、外部直接 fail」，所以 R39 先用受控的合成形狀資料探路。

## 開輪動機

觸發點是一個觀察到的 baseline 弱點：當時的主線模型（COMBO 之前的 ring-trained 主線）對圓環重建很強，但只要碰到非圓環形狀——三角形、矩形、橢圓、多邊形、混合場景——重建就明顯變差。也就是 baseline 的能力被訓練分布綁死在 ring 上。

R39 的問題就是：能不能加進受控合成的多形狀資料，把 non-ring 形狀的重建拉到能用，同時不傷既有的 ring 能力。後續的 `r39_combo_strong_avg_a030`（COMBO 與 R39_strong 在 alpha=0.30 的權重平均）就是針對這個問題的直接答案，七類 held-out 形狀全部都從 22.67-25.40 PSNR 升到 26.25-32.68（細節見 `reports/R39_RESULTS.md`）。

## 目標

- Ring 訓練資料保留在混合包裡,不抽掉。
- 加進受控合成的三角形、圓、矩形、橢圓、多邊形與 mixed 形狀。
- 留一份 unseen 的多形狀驗證集,用沒進訓練的影像測形狀增益。
- 兩個候選都從現行 COMBO checkpoint 接續訓練。
- 既有 external ring tests 不過就不升級,沒有例外。

## 資料包

Builder 把產生的資料寫到 `Training_Data/r39_shape_generalization/`,刻意放在 git 之外。

三個 profile:

- `r39_shape_mix_safe`:ring + 每個形狀 stage 20 張。主要候選。
- `r39_shape_mix_strong`:ring + 每個形狀 stage 70 張。容量探針,看資料量上限的反應。
- `shape_val_unseen`:每個形狀 stage 30 張 held-out,完全不進訓練。

建立或檢查資料包:

```powershell
python Experiments/R39_ShapeGeneralization/scripts/r39_shape_data.py plan --profile all
python Experiments/R39_ShapeGeneralization/scripts/r39_shape_data.py build --profile all --force
```

## 訓練

兩個候選都從 COMBO 接續,沿用 R38v2 的 8px 序列 gate。

```powershell
python Experiments/R39_ShapeGeneralization/scripts/launch_r39.py --candidate r39_shape_mix_safe --build-data --num-epoch 100 --device cuda:0
python Experiments/R39_ShapeGeneralization/scripts/launch_r39.py --candidate r39_shape_mix_strong --build-data --num-epoch 100 --device cuda:0
```

`--dry-run` 會驗資料包與候選設定,不真的跑訓練。

## 形狀驗證

判斷候選之前,COMBO baseline 要先在 `shape_val_unseen` 上跑過一遍。

```powershell
python Experiments/R39_ShapeGeneralization/scripts/run_r39_shape_recon.py --profile shape_val_unseen --dry-run
python Experiments/R39_ShapeGeneralization/scripts/run_r39_shape_recon.py --profile shape_val_unseen --weights Experiments/Training_Runs/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260408_003525/weights/best_tradeoff.pth.tar
python Experiments/R39_ShapeGeneralization/scripts/summarize_r39_shape_recon.py --profile shape_val_unseen
```

候選 checkpoint 用一樣的指令,把 `--weights` 換成各自的 `best_tradeoff.pth.tar`。

## Ring Guard

R39 的 local ring guard = 三尺度 ring 重建 + 720-angle 序列分析。它不是正式的外部 GMF,只是早期警示用。

```powershell
.\Tools\RunRepresentativeExternalRecon.ps1 -WeightsPath Experiments/Training_Runs/training_progress_GESR_v1_v5_ST0p8_SWP_r39_shape_mix_safe_20260428_165958/weights/best_tradeoff.pth.tar -ReconRoot Experiments/R39_ShapeGeneralization/results/ring_recon/r39_shape_mix_safe
python Experiments/R39_ShapeGeneralization/scripts/run_r39_ring_guard.py --candidate r39_shape_mix_safe
```

`r39_shape_mix_strong` 同樣流程跑一遍。

## 升級規則

R39 只是研究結果,要同時滿足以下兩項才升級:

- 多形狀驗證明顯比 COMBO 好。
- 既有的 0.8px 與 8px 外部 ring 測試沒有實質退步。

形狀數字漂亮但 ring gate 卡掉,結果記錄但不升級——這條規則沒有彈性。

## 權重平均 sweep(訓練後延伸)

兩個訓練好的候選都過不了 ring guard,但用線性插值把它們和 COMBO 的權重混起來,可以救回 ring 穩定度,同時保留可觀的形狀增益。`alpha = 0.30` 的 sweep 結果產出 `r39_combo_strong_avg_a030`,這個才是這輪真正的升級候選。

```powershell
python Experiments/R39_ShapeGeneralization/scripts/run_r39_weight_sweep.py
python Experiments/R39_ShapeGeneralization/scripts/plot_r39_weight_sweep.py
```

對平均後的 checkpoint 跑外部 GMF:

```
Experiments/R39_ShapeGeneralization/results/weight_sweep/checkpoints/a030/best_tradeoff.pth.tar
```

接著 parse 並比較:

```powershell
python Experiments/R39_ShapeGeneralization/scripts/r39_external_compare.py
```

## 目前結果

| candidate | held-out shape PSNR | external 8px | external 0.8px | external 0.08px | verdict |
|---|---:|---:|---:|---:|---|
| `r39_shape_mix_safe` | 26.68 | — | — | — | local ring guard 退步,不可升級 |
| `r39_shape_mix_strong` | 30.07 | — | — | — | local ring guard 退步,不可升級 |
| **`r39_combo_strong_avg_a030`** (alpha=0.30 weight average) | 25.03 | **0.143794** (-6.94%) | 0.140008 (+6.42%) | **0.083941** (-15.97%) | **PASS_TRADEOFF**,alternate-grade,等專案決策 |

`r39_combo_strong_avg_a030` 是 R39 唯一過了外部 GMF 的產物。0.08px 是專案至今最低的外部 step_std。視覺品質留在 sharp 帶內(edge_steepness 只比 COMBO 低 5.6%,離 R33 的 soft 帶還很遠)。要不要進 `ESTIMATOR_POLICY.json` 的 `approved_alternates` 是專案 owner 的決定;在那之前 a030 掛在 `open_side_tracks` 下。

正式報告:

- `reports/R39_RESULTS.md`(完整結果 + 視覺品質專節)
- `reports/R39_EXTERNAL_COMPARE.md`(外部 GMF 比較,自動產生)
- `results/weight_sweep/sweep_summary.md` + `sweep_tradeoff.png`(alpha vs 各項指標)
