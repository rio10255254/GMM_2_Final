# R54 Geometry Root-Cause Probe

## Verdict

Do not start another long Lab training run yet. Existing evidence already
shows that reconstruction is damaging real checkboard corner geometry, and
the strict-rectangle CAD labels are usable only as masked local supervision.

## Corner Damage Evidence

- Raw input >5 px corner errors: 1.676%
- Best reconstruction by >5 px rate: lab_r40_best_tradeoff (24.581%)
- Worst reconstruction: lab_r53_realistic_latest (58.939%)
- R53 latest minus Lab R40 >5 px rate: 34.358 percentage points
- Next gate after follow-up: `do_not_continue_from_r54_edgeband_as_training_candidate`

## CAD GT / Mask Evidence

- Valid CAD-reference pairs: 36
- High-quality probe pairs: 36
- Median reliable-mask coverage: 0.0161
- Max CAD edge p95 error: 1.910 px
- Initial label policy: `train_only_inside_reliable_mask`
- Follow-up label policy: `cad_gt_inside_reliable_mask_plus_cad_edge_band_source_elsewhere`

## Hypothesis Table

| Hypothesis | Status | Evidence | Decision |
|---|---|---|---|
| H1_reconstruction_itself_damages_real_corners | supported | raw >5px=1.676%, worst=lab_r53_realistic_latest 58.939% | must gate on real-corner damage before long training |
| H2_more_generic_data_is_enough | contradicted | R53 used a larger realistic mix but worsened large-corner errors. | do not repeat another long generic-data run first |
| H3_strict_rect_cad_gt_can_support_small_probe | supported | 36/36 valid CAD pairs pass edge-quality filters | train_only_inside_reliable_mask |
| H4_psf_is_the_only_root_cause | not_proven | R51/R52/R53 changed blur/data strategy but large-corner errors remained. | test PSF only after a masked small-sample probe isolates the geometry target |

## Selected Small-Probe Pairs

| Pair | Coverage | Edge p95 px | Edge within 2 px | Components |
|---|---:|---:|---:|---:|
| CB20260613_0002 | 0.2110 | 0.955 | 1.000 | 2 |
| CB20260613_0006 | 0.2020 | 0.955 | 1.000 | 3 |
| CB20260613_0007 | 0.2019 | 0.955 | 1.000 | 3 |
| CB20260613_0004 | 0.1057 | 0.955 | 1.000 | 1 |
| CB20260613_0001 | 0.1056 | 0.955 | 1.000 | 1 |
| CB20260613_0003 | 0.1055 | 0.955 | 1.000 | 1 |
| CB20260613_0034 | 0.0674 | 0.955 | 1.000 | 1 |
| CB20260613_0011 | 0.0663 | 0.955 | 0.998 | 4 |
| CB20260613_0036 | 0.0662 | 0.955 | 0.999 | 4 |
| CB20260613_0009 | 0.0662 | 0.955 | 0.999 | 4 |
| CB20260613_0010 | 0.0662 | 0.955 | 0.998 | 4 |
| CB20260613_0039 | 0.0661 | 0.955 | 0.999 | 4 |

## Next Experiment Gate

This gate has now been executed. The corrected edge-band masked small-overfit
probe learned the selected CAD regions, but the epoch20 checkpoint failed the
real `20250605_checkboard` corner gate. The issue is therefore not simply
model capacity on CAD edges; it is real-image generalization and output drift.

Do not continue from the R54 edge-band checkpoint as a formal Lab training
candidate. See `reports/R54_MASKED_SMALL_PROBE.md` and
`reports/R54_CHECKBOARD_VALIDATION.md`.

## Artifacts

- Diagnosis JSON: `LabSystem_MOSR/Experiments/R54_GeometryRootCauseProbe/results/root_cause_probe/r54_root_cause_diagnosis.json`
- Hypothesis table: `LabSystem_MOSR/Experiments/R54_GeometryRootCauseProbe/results/root_cause_probe/r54_hypothesis_table.csv`
- Selected probe pairs: `LabSystem_MOSR/Experiments/R54_GeometryRootCauseProbe/results/root_cause_probe/r54_small_overfit_probe_pairs.csv`
- Overlay contact sheet: `LabSystem_MOSR/Experiments/R54_GeometryRootCauseProbe/results/root_cause_probe/r54_small_probe_overlays.png`
- Follow-up masked small-probe report: `LabSystem_MOSR/Experiments/R54_GeometryRootCauseProbe/reports/R54_MASKED_SMALL_PROBE.md`
- Follow-up real checkboard validation report: `LabSystem_MOSR/Experiments/R54_GeometryRootCauseProbe/reports/R54_CHECKBOARD_VALIDATION.md`
