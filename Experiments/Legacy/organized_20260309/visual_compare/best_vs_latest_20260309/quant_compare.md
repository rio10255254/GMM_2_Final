# 三張樣本的代理量化比較

比較對象：
Experiments/Legacy/organized_20260307/selected/runs/training_progress_GESR_v1_v5_ST8_SWP_stdg_20260307_135625/weights/best_tradeoff.pth.tar
Experiments/Training_Runs/training_progress_GESR_v1_v5_ST0p08_SWP_mcf_20260309_231113/weights/best_tradeoff.pth.tar

平均結果：
- best 平均 edge_width_10_90_px: 10.674
- latest 平均 edge_width_10_90_px: 10.573
- latest-best edge_width: -0.100
- best 平均 grad_q99_5: 89.295
- latest 平均 grad_q99_5: 89.040
- latest-best grad_q99_5: -0.255
- best 平均 bg_hp_std: 0.424
- latest 平均 bg_hp_std: 0.420
- latest-best bg_hp_std: -0.004

## VisionTop_20251029182653732.bmp
- crop_xy: [699, 819]
- best: width=14.215, grad_q99_5=81.571, bg_hp_std=0.446
- latest: width=14.115, grad_q99_5=80.727, bg_hp_std=0.449
- delta latest-best: width=-0.100, grad=-0.844, bg_hp_std=+0.003

## VisionTop_20251029183552176.bmp
- crop_xy: [372, 1398]
- best: width=8.127, grad_q99_5=84.894, bg_hp_std=0.411
- latest: width=7.993, grad_q99_5=85.410, bg_hp_std=0.403
- delta latest-best: width=-0.134, grad=+0.516, bg_hp_std=-0.008

## VisionTop_20251029184451292.bmp
- crop_xy: [589, 1088]
- best: width=9.679, grad_q99_5=101.421, bg_hp_std=0.414
- latest: width=9.612, grad_q99_5=100.984, bg_hp_std=0.407
- delta latest-best: width=-0.067, grad=-0.437, bg_hp_std=-0.007
