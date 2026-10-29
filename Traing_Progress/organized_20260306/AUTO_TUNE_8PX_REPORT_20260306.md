# Auto Tune 8px Report

## Goal

Primary objective:
- boundary position reconstruction accuracy
- sensitivity to real `1 um = 8 px` displacement for downstream `GMF / PM`

Secondary objective:
- sharper, more realistic boundary appearance
- recover texture only when it does not damage displacement stability

## What Changed

### Training / validation logic

- Added `TRAIN_INCLUDE_SUBDIRS` support in [GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py](../../Model/GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py) so autotune can train on explicit stage subsets instead of only excluding folders.
- Added true `monitor_shift` GMF proxy validation:
  - uses one fixed monitor image
  - synthesizes a known-step sequence with `GMF_MONITOR_STEP_DY = 8`
  - uses center-frame reference to avoid cumulative search drift
- GMF proxy now evaluates a real known-step sequence rather than unrelated validation samples.

### Training data

- Updated [Data_Simulaion.py](../../Training_Data/Data_Simulaion.py):
  - restored `RUN_STAGE_IDS = []` for normal manual use
  - made stage `08/09/10` milder and cleaner for curve-boundary learning
  - added `stage_13_curve_clean_general`
  - added `stage_14_annulus_edge_defect_focus`
- Re-generated stages `08/09/10/13/14`
- Re-ran PSF convolution for the same stages

### Auto tune strategy

- Updated [GeoEdgeAlignSR_v1_AutoTuneTrain.py](../../Model/GeoEdgeAlignSR_v1_AutoTuneTrain.py):
  - expected known step: `dx=0`, `dy=8`
  - proxy source: `monitor_shift`
  - reduced validation cost enough to make repeated sweep/final feasible
  - candidate families:
    - `step8_curve_general`
    - `step8_curve_sharp`
    - `step8_general_balanced`
    - `step8_annulus_priority`

## Sweep Result

Sweep command used:

```powershell
python -u Model/GeoEdgeAlignSR_v1_AutoTuneTrain.py --sweep-epochs 3 --final-epochs 36 --deterministic
```

Sweep ranking:

| candidate | score | step_err | pos_std | pass02 |
|---|---:|---:|---:|---:|
| `step8_curve_sharp` | `-40.310501` | `0.000000` | `0.000000` | `0.000000` |
| `step8_curve_general` | `-41.106630` | `0.000000` | `0.000000` | `0.000000` |
| `step8_annulus_priority` | `-41.256918` | `0.000000` | `0.000000` | `0.000000` |
| `step8_general_balanced` | `-45.371374` | `0.500000` | `1.482600` | `0.000000` |

Autotune selected:
- `step8_curve_sharp`

Sweep intermediate run folders were removed during cleanup after extracting ranking results.

## Final Run

Final run directory:
- [training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_AUTO_FINAL_step8_curve_sharp_20260306_200332](selected/runs/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_AUTO_FINAL_step8_curve_sharp_20260306_200332)

Chosen checkpoint:
- [best_tradeoff.pth.tar](selected/runs/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_AUTO_FINAL_step8_curve_sharp_20260306_200332/weights/best_tradeoff.pth.tar)

Reason:
- this checkpoint was written at `2026-03-06 20:19:40`
- later epochs kept improving visual sharpness and `SSIM`
- but later epochs clearly worsened `GMF / PM` relevant step statistics
- user priority is displacement accuracy first, visual sharpness second

## Selected Best Point

Adopted best point: `epoch 6`

`epoch 6` metrics:

| metric | value |
|---|---:|
| `val_rec` | `0.0054886` |
| `val_ssim` | `0.9134674` |
| `metric_edge_width` | `10.4333` |
| `metric_hf_proxy` | `0.0000323` |
| `proxy_score_mean` | `22.7630` |
| `proxy_score_p10` | `22.4465` |
| `proxy_step_err` | `0.3333` |
| `proxy_pos_step_std_sum` | `0.0000` |
| `kpi_step_mean_err` | `0.0196` |
| `kpi_step_std` | `0.5938` |
| `kpi_outlier_rate` | `0.3333` |
| `gmf_obj` | `33.8141` |

## Why I Stopped Early

I stopped the final run manually after `epoch 20`.

Reason:
- from `epoch 10` onward, images became visually cleaner and narrower
- but known-step stability degraded
- this is the exact failure direction we wanted to avoid

Comparison:

| epoch | val_ssim | edge_width | kpi_step_mean_err | kpi_step_std | kpi_outlier_rate | gmf_obj |
|---|---:|---:|---:|---:|---:|---:|
| `6` | `0.9135` | `10.4333` | `0.0196` | `0.5938` | `0.3333` | `33.8141` |
| `10` | `0.9448` | `7.0172` | `1.4114` | `2.5999` | `1.0000` | `29.9110` |
| `14` | `0.9555` | `5.9024` | `4.3256` | `6.9220` | `0.6667` | `28.4188` |
| `16` | `0.9586` | `5.8158` | `4.4922` | `6.8272` | `0.8333` | `28.2971` |
| `18` | `0.9608` | `5.7730` | `4.6749` | `6.3651` | `0.6667` | `28.3105` |

Interpretation:
- later epochs are sharper and visually nicer
- but they are materially worse for the displacement task
- the model starts drifting toward appearance optimization rather than stable 8px step reconstruction

## Current Adopted Version

Current adopted manual inference weight path is already updated in:
- [GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py](../../Model/GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py)

Path now points to:

```text
Traing_Progress/organized_20260306/selected/runs/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_AUTO_FINAL_step8_curve_sharp_20260306_200332/weights/best_tradeoff.pth.tar
```

## Practical Conclusion

This round produced a better-aligned `8 px` strategy than the previous tiny-shift-focused version.

The main outcome is not "the sharpest image".
The main outcome is:
- explicit `8 px` validation
- curve-focused but not annulus-only data
- a selected checkpoint before GMF stability degraded

If continuing later, the next direction should be:
- keep the `step8_curve_sharp` data family
- reduce the late-stage tendency toward oversharpening / GMF drift
- consider selecting final checkpoints directly by `kpi_step_mean_err + kpi_step_std + outlier_rate`, with visual metrics as guards only
