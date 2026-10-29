# Previous Round Organized File Map

This file organizes the previous round so the next run can start without searching through the whole project.

Large outputs stay in their original folders. This index explains what each item is, why it matters, and whether it should be used, kept, or treated only as a diagnostic record.

## A. Handoff And Progress Notes

| item | what it is | status | path |
|---|---|---|---|
| Current handoff folder | The clean starting packet for the next round | use first | `Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/next_round_20260623_v16_handoff` |
| Older v15 target folder | The earlier target and archive index made before this cleanup | keep as prior note | `Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/next_round_20260623_v15_step_guard` |
| R61 progress note | Running narrative of what the R61 line has tried and learned | keep updating | `Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/R61_PROGRESS_20260623.md` |

## B. v14 Training Result

| item | what it is | status | path |
|---|---|---|---|
| v14 best checkpoint | Best saved weight from the full v14 motion-texture run | use as predecessor | `Thesis_MOSR_Evidence/LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r61_motion_texture_v11base_dualgate_boundary_focus_motiontexture_full_e8_20260623_150217/weights/best_tradeoff.pth.tar` |
| v14 training folder | Full training output folder, including weights and run artifacts | keep | `Thesis_MOSR_Evidence/LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r61_motion_texture_v11base_dualgate_boundary_focus_motiontexture_full_e8_20260623_150217` |
| v14 training stdout | Main command output from the 8-epoch run | keep for audit | `Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/training_logs/r61_motion_texture_v11base_full_e8_20260623_150211.out.log` |
| v14 training stderr | Warnings and stderr from the 8-epoch run | keep for audit | `Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/training_logs/r61_motion_texture_v11base_full_e8_20260623_150211.err.log` |
| v14 dataset package | Old data plus camera-texture known-motion data | reuse as backbone | `Thesis_MOSR_Evidence/LabSystem_MOSR/Training_Data/r61_universal_boundary_generalization/hs100mg_basler/r61_universal_boundary_train_motion_texture_guard_v14` |

## C. Simulated Boundary Validation

| item | what it is | status | path |
|---|---|---|---|
| v14 diverse phantom validation | 96-case simulated boundary validation output | use as comparison | `R61_motiontexture_dpv96_20260623/diverse_phantom_validation_20260623_164241` |
| Boundary metrics table | Per-case boundary measurement table | use | `R61_motiontexture_dpv96_20260623/diverse_phantom_validation_20260623_164241/boundary_metrics.csv` |
| v14 gate vs R39 | Strict boundary gate against the R39 a970 baseline | use | `R61_motiontexture_dpv96_20260623/diverse_phantom_validation_20260623_164241/gate_vs_r39.json` |
| v14 gate vs R8 | Strict boundary gate against R8 | use | `R61_motiontexture_dpv96_20260623/diverse_phantom_validation_20260623_164241/gate_vs_r8.json` |

Key result:

- v14 overall mean is slightly better than R39.
- v14 still fails five strict groups: bright, 0 px bias, 0.5 px bias, annulus, ellipse.

## D. 20260603 Real Sequence Validation

| item | what it is | status | path |
|---|---|---|---|
| v14 real reconstruction case | The 11 reconstructed 20260603 frames for v14 | use as predecessor | `Analyses/Reconstruct_Progress/20260603_external_gmf_prepare/23_r61_motion_texture_v11base_full_e8_best` |
| v14 real preview | Raw versus v14 visual preview | inspect if needed | `Analyses/Reconstruct_Progress/20260603_external_gmf_prepare/23_r61_motion_texture_v11base_full_e8_best/preview_raw_vs_v14.png` |
| Real motion JSON | Main local-motion summary including v14 | use | `Analyses/Reconstruct_Progress/20260603_external_gmf_prepare/local_motion_probe_summary_after_r61_motiontexture_full_e8.json` |
| Real motion CSV | Row-level local-motion table | use for detailed checks | `Analyses/Reconstruct_Progress/20260603_external_gmf_prepare/local_motion_probe_summary_after_r61_motiontexture_full_e8.csv` |
| Real motion readable table | Human-readable summary table | use for quick review | `Analyses/Reconstruct_Progress/20260603_external_gmf_prepare/local_motion_probe_summary_after_r61_motiontexture_full_e8.md` |

Key result:

- Raw tail std dy: 0.268818 px.
- R39 tail std dy: 0.278475 px.
- v14 tail std dy: 0.276390 px.
- v14 is better than R39 here, but still worse than raw.

## E. Step Raw Data And Staged Inputs

| item | what it is | status | path |
|---|---|---|---|
| Step source images | The original Step capture folder with 788 BMP files | source of truth | `Step` |
| Step selection report | Readable report explaining the selected 1 um sequence | use | `Analyses/Step_analysis_20260623/STEP_1UM_SELECTION_REPORT.md` |
| Step baseline JSON | Machine-readable Step grouping summary | use | `Analyses/Step_analysis_20260623/step_baseline_summary.json` |
| Same-position pairs | Repeat-capture baseline pairs | use | `Analyses/Step_analysis_20260623/within_position_pairs.csv` |
| Adjacent 0.1 um pairs | Raw adjacent-position probe | keep | `Analyses/Step_analysis_20260623/adjacent_0p1um_pairs.csv` |
| Selected 1 um positions | Positions 0, 10, 20, ..., 390 | use | `Analyses/Step_analysis_20260623/selected_1um_positions.csv` |
| Selected 1 um pairs | Two replicate streams for the selected +10-position sequence | use | `Analyses/Step_analysis_20260623/selected_1um_pairs.csv` |
| Full-size selected input | 80 selected input images at full 5120 image size | keep, but do not infer full-size without tiling | `Analyses/Step_analysis_20260623/selected_1um_input/bmp` |
| Center-crop selected input | 80 selected input images cropped to center 2048 x 2048 | use for current inference | `Analyses/Step_analysis_20260623/selected_1um_input_center2048/bmp` |

Key result:

- Raw same-position repeat median is about 0.0196 px on the center crop.
- Raw selected +10-position median motion is about 0.7428 px on the center crop.
- User calibration expects 1 um to be 8.0 px, so raw Step scale is still unresolved.

## F. Step R39 And v14 Reconstruction Outputs

| item | what it is | status | path |
|---|---|---|---|
| R39 center-crop Step output | 80-frame PSF-off R39 Step reconstruction | use as strong reference | `Analyses/Step_analysis_20260623/r61_step_1um_center2048_recon_package/01_r39_a970_step_1um_center2048/bmp` |
| v14 center-crop Step output | 80-frame PSF-off v14 Step reconstruction | use as predecessor | `Analyses/Step_analysis_20260623/r61_step_1um_center2048_recon_package/02_v14_motion_texture_step_1um_center2048/bmp` |
| Raw/R39/v14 Step summary | Combined readable Step motion table | use | `Analyses/Step_analysis_20260623/STEP_MOTION_PROBE_CENTER2048_RAW_R39_V14_SUMMARY.md` |
| Raw/R39/v14 Step JSON | Combined machine-readable Step motion summary | use | `Analyses/Step_analysis_20260623/step_motion_probe_center2048_raw_r39_v14_summary.json` |
| Raw/R39/v14 path list | The exact folders passed to the Step motion-probe script | use for reruns | `Analyses/Step_analysis_20260623/step_center2048_raw_r39_v14_paths.tsv` |
| Raw/R39/v14 preview | Visual preview comparing raw, R39, and v14 on two Step positions | inspect | `Analyses/Step_analysis_20260623/step_center2048_raw_r39_v14_preview.png` |
| v14 triple gate | Combined boundary, 20260603, and Step verdict for v14 | use as baseline verdict | `Analyses/Step_analysis_20260623/triple_gate_v14_boundary_real_step_vs_raw_r39.json` |

Key result:

- R39 Step same-position repeat median: 0.134328 px.
- R39 selected +10-position median motion: 8.025572 px.
- v14 Step same-position repeat median: 0.133604 px.
- v14 selected +10-position median motion: 8.026748 px.
- v14 Step std dx is only 0.0000249 px worse than R39, but the strict gate still marks it as fail.

## G. Step Guard Tooling Created In The Previous Round

| item | what it is | status | path |
|---|---|---|---|
| Step motion probe script | Measures repeat-capture and selected +10-position image motion | use | `Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/scripts/probe_step_sequence_motion.py` |
| Triple gate script | Combines simulated boundary, 20260603 real motion, and Step checks | use | `Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/scripts/score_triple_generalization_gate.py` |
| Step motion probe tests | Regression tests for Step pair construction and summaries | keep running | `Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/tests/test_probe_step_sequence_motion.py` |
| Triple gate tests | Regression tests for the combined gate | keep running | `Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/tests/test_score_triple_generalization_gate.py` |

## H. Diagnostic Or Failed Records

| item | what it is | status | path |
|---|---|---|---|
| Full-size R39 Step attempt | Full 5120 inference attempt that failed with CUDA out-of-memory | diagnostic only | `Analyses/Step_analysis_20260623/r61_step_1um_recon_package` |
| v14 stale center-crop launch attempt | Earlier v14 launch attempt that stalled before valid output | diagnostic only | `Analyses/Step_analysis_20260623/r61_step_1um_center2048_recon_package/_r61_real_sample_runtime_20260623_191526` |
| Center-crop smoke output | Small smoke-test output used before the full 80-frame run | diagnostic only | `Analyses/Step_analysis_20260623/r61_step_1um_center2048_smoke_reconstruction_outputs` |

Do not delete these yet, but do not use them as successful results.

## I. Numbers To Carry Into The Next Round

| metric | value |
|---|---:|
| v14 simulated boundary mean | 0.483153 px |
| R39 simulated boundary mean | 0.483705 px |
| v14 strict boundary result | fail, five small group failures |
| raw 20260603 tail std dy | 0.268818 px |
| R39 20260603 tail std dy | 0.278475 px |
| v14 20260603 tail std dy | 0.276390 px |
| Step center-crop raw repeat median | 0.019576 px |
| Step center-crop raw selected +10 median motion | 0.742768 px |
| Step center-crop R39 repeat median | 0.134328 px |
| Step center-crop R39 selected +10 median motion | 8.025572 px |
| Step center-crop v14 repeat median | 0.133604 px |
| Step center-crop v14 selected +10 median motion | 8.026748 px |
| User-calibrated expected Step 1 um motion | 8.000000 px |

