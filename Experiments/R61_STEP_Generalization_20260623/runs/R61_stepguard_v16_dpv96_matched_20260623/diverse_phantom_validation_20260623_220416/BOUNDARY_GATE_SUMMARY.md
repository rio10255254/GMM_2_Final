# v16 Step-Guard Diverse Phantom Boundary Gate Summary

Candidate metrics: `Experiments/R61_STEP_Generalization_20260623/runs/R61_stepguard_v16_dpv96_matched_20260623/diverse_phantom_validation_20260623_220416/boundary_metrics.csv`

## vs R39

pass: `False`

| metric | baseline | v16 | delta | passed |
|---|---:|---:|---:|---|
| mean_chamfer_px | 0.483704669 | 0.482734433 | -0.000970236 | True |
| p95_chamfer_px | 1.050637364 | 1.050637364 | 0.000000000 | True |
| max_chamfer_px | 2.361819625 | 2.361819625 | 0.000000000 | True |

Failures:

- bias_px=0 mean_chamfer_px: baseline 0.268290658, v16 0.269013006, delta 0.000722348
- bias_px=0.5 mean_chamfer_px: baseline 0.268290658, v16 0.269013006, delta 0.000722348

## vs R8

pass: `False`

| metric | baseline | v16 | delta | passed |
|---|---:|---:|---:|---|
| mean_chamfer_px | 0.484760639 | 0.482734433 | -0.002026206 | True |
| p95_chamfer_px | 1.056318998 | 1.050637364 | -0.005681634 | True |
| max_chamfer_px | 2.395643830 | 2.361819625 | -0.033824205 | True |

Failures:

- bias_px=0 mean_chamfer_px: baseline 0.268308640, v16 0.269013006, delta 0.000704365
- bias_px=0.5 mean_chamfer_px: baseline 0.268308640, v16 0.269013006, delta 0.000704365

## vs v14

pass: `False`

| metric | baseline | v16 | delta | passed |
|---|---:|---:|---:|---|
| mean_chamfer_px | 0.483153311 | 0.482734433 | -0.000418877 | True |
| p95_chamfer_px | 1.050637364 | 1.050637364 | 0.000000000 | True |
| max_chamfer_px | 2.361819625 | 2.361819625 | 0.000000000 | True |

Failures:

- bias_px=0 mean_chamfer_px: baseline 0.268896653, v16 0.269013006, delta 0.000116353
- bias_px=0.5 mean_chamfer_px: baseline 0.268896653, v16 0.269013006, delta 0.000116353
- bias_px=1 mean_chamfer_px: baseline 0.179135403, v16 0.179173949, delta 0.000038546
- shape=circle mean_chamfer_px: baseline 0.488486616, v16 0.488577523, delta 0.000090907
