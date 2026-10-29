# R39 a030 × R40 a043 互補權重平均 sweep

## 動機

a030 與 R40 a043 在外部 GMF 三尺度上的取捨方向互補（2026-05-11 量測）：

| 候選 | 8 px Δ | 0.8 px Δ | 0.08 px Δ |
|---|---:|---:|---:|
| R39 a030 | `−6.94%` | `+6.42%` | `−15.97%` |
| R40 a043 | `−5.91%` | `−3.15%` | `+21.52%` |

兩者 8 px 改善幅度近乎相同；a030 改善 0.08 px 但 0.8 px 退步、a043 改善 0.8 px 但 0.08 px 退步。本實驗線性平均兩個 checkpoint，看互補取捨能不能讓三尺度都進 7 % 替代容忍區。

## 中間 alpha 平均 checkpoint

α=0.0 是純 a030，α=1.0 是純 a043，兩端已有外部 GMF 結果。中間 alpha 都是 R39 weight_sweep 的 `interpolate_state_dicts` 線性插值：

| α | checkpoint |
|---:|---|
| 0.25 | `Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/checkpoints/a025/best_tradeoff.pth.tar` |
| 0.50 | `Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/checkpoints/a050/best_tradeoff.pth.tar` |
| 0.75 | `Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/checkpoints/a075/best_tradeoff.pth.tar` |

## 外部 ring 三尺度重建（每 α 跑一次）

```powershell
powershell -ExecutionPolicy Bypass -File Tools/RunRepresentativeExternalRecon.ps1 -WeightsPath "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/checkpoints/a025/best_tradeoff.pth.tar" -ReconRoot "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/external_recon/a025"
powershell -ExecutionPolicy Bypass -File Tools/RunRepresentativeExternalRecon.ps1 -WeightsPath "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/checkpoints/a050/best_tradeoff.pth.tar" -ReconRoot "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/external_recon/a050"
powershell -ExecutionPolicy Bypass -File Tools/RunRepresentativeExternalRecon.ps1 -WeightsPath "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/checkpoints/a075/best_tradeoff.pth.tar" -ReconRoot "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/external_recon/a075"
```

完成後 BMP 結構：

```
external_recon/aXXX/reconstruct_progress_best_tradeoff_in_Cropped_Output_<ts>/
    pitch1um_y_100_odd/   (101 張 → 對應 8 px)
    pitch0p1um_y_60_odd/  (61 張 → 對應 0.8 px)
    pitch0p01um_y_40_odd/ (41 張 → 對應 0.08 px)
```

## 送外部 GMF 工具後

把每個 α、每個 pitch 的 BMP 餵給外部 GMF 視覺定位工具，產生 `GMF_score.txt`，放回：

```
external_recon/aXXX/external_gmf/pitch{8px,0p8px,0p08px}/GMF_score.txt
```

然後跑 `r40_external_compare.py` 解析（一次一個 α）。
