# Previous Round Archive Index - v14 Motion Texture and Step Guard

This folder is an index for the previous long run. It does not move or duplicate the large artifacts. Keep the source paths stable so existing scripts and reports continue to work.

## Why This Archive Exists

The last round produced training outputs, validation outputs, real reconstruction outputs, Step baseline files, previews, and progress notes. The purpose of this index is to make the next long run reproducible without searching across the whole project.

## Main Outcome

v14 improved the simulated boundary mean and gave the best R61-series 20260603 local-motion tail stability so far, but it did not pass the strict gate. It still failed several boundary groups and still did not beat raw input on 20260603 real-motion stability.

Step was inspected and converted into a 1 um commanded-step selection, but the measured pixel motion does not match the user-provided calibration. Treat Step as a required next-round validation dataset with an open scale caveat.

After this index was first created, a center-crop Step guard was added. Raw center-crop Step preserved the same measured motion as the full image ROI, and R39 a970 center-crop inference completed for all 80 selected frames. Full-size Step inference remains unusable without tiling because it ran out of GPU memory.

## Core Training Artifact

| item | role | path |
|---|---|---|
| v14 best checkpoint | best model weight from the motion-texture full run | `LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r61_motion_texture_v11base_dualgate_boundary_focus_motiontexture_full_e8_20260623_150217/weights/best_tradeoff.pth.tar` |
| v14 training folder | full training progress, weights, plots, logs | `LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r61_motion_texture_v11base_dualgate_boundary_focus_motiontexture_full_e8_20260623_150217` |
| v14 stdout log | command output for the full 8-epoch run | `LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/training_logs/r61_motion_texture_v11base_full_e8_20260623_150211.out.log` |
| v14 stderr log | warnings from the full 8-epoch run | `LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/training_logs/r61_motion_texture_v11base_full_e8_20260623_150211.err.log` |
| v14 dataset package | training package with old data plus camera-texture known-motion data | `LabSystem_MOSR/Training_Data/r61_universal_boundary_generalization/hs100mg_basler/r61_universal_boundary_train_motion_texture_guard_v14` |

## Boundary Validation Artifact

| item | role | path |
|---|---|---|
| v14 diverse phantom run | 96-case simulated boundary validation output | `R61_motiontexture_dpv96_20260623/diverse_phantom_validation_20260623_164241` |
| v14 boundary metrics | per-case boundary measurements | `R61_motiontexture_dpv96_20260623/diverse_phantom_validation_20260623_164241/boundary_metrics.csv` |
| v14 gate vs R39 | strict simulated boundary gate against R39 a970 | `R61_motiontexture_dpv96_20260623/diverse_phantom_validation_20260623_164241/gate_vs_r39.json` |
| v14 gate vs R8 | strict simulated boundary gate against R8 | `R61_motiontexture_dpv96_20260623/diverse_phantom_validation_20260623_164241/gate_vs_r8.json` |

## Real 20260603 Artifact

| item | role | path |
|---|---|---|
| v14 real reconstruction case | 11 reconstructed frames for the 20260603 sequence | `Analyses/Reconstruct_Progress/20260603_external_gmf_prepare/23_r61_motion_texture_v11base_full_e8_best` |
| v14 real preview | side-by-side raw versus v14 preview | `Analyses/Reconstruct_Progress/20260603_external_gmf_prepare/23_r61_motion_texture_v11base_full_e8_best/preview_raw_vs_v14.png` |
| real motion summary json | local motion probe including v14 | `Analyses/Reconstruct_Progress/20260603_external_gmf_prepare/local_motion_probe_summary_after_r61_motiontexture_full_e8.json` |
| real motion summary csv | row-level local motion probe output | `Analyses/Reconstruct_Progress/20260603_external_gmf_prepare/local_motion_probe_summary_after_r61_motiontexture_full_e8.csv` |
| real motion summary markdown | readable table for local motion probe | `Analyses/Reconstruct_Progress/20260603_external_gmf_prepare/local_motion_probe_summary_after_r61_motiontexture_full_e8.md` |

## Step Baseline and 1 um Selection Artifact

| item | role | path |
|---|---|---|
| Step source images | 788 raw BMP files | `Step` |
| Step baseline report | readable summary of Step grouping and selected 1 um sequence | `Analyses/Step_analysis_20260623/STEP_1UM_SELECTION_REPORT.md` |
| Step baseline summary | machine-readable summary of Step checks | `Analyses/Step_analysis_20260623/step_baseline_summary.json` |
| Step same-position pairs | repeat-capture baseline for two frames at the same position | `Analyses/Step_analysis_20260623/within_position_pairs.csv` |
| Step 0.1 um adjacent pairs | raw adjacent-position probe | `Analyses/Step_analysis_20260623/adjacent_0p1um_pairs.csv` |
| Step selected 1 um positions | selected positions 0, 10, 20, ..., 390 | `Analyses/Step_analysis_20260623/selected_1um_positions.csv` |
| Step selected 1 um pairs | pair manifest for the two replicate 1 um sequences | `Analyses/Step_analysis_20260623/selected_1um_pairs.csv` |
| Step all sliding 1 um probe | all possible position +10 probes | `Analyses/Step_analysis_20260623/all_sliding_1um_pairs_probe.csv` |
| Step selected preview | first selected 1 um frames, replicate 0 | `Analyses/Step_analysis_20260623/selected_1um_first8_rep0_preview.png` |

## Step Guard Addendum

| item | role | path |
|---|---|---|
| Step full selected input | hardlinked 80-image selected 1 um input, full 5120 image size | `Analyses/Step_analysis_20260623/selected_1um_input/bmp` |
| Step center-crop selected input | 80-image selected 1 um input cropped to center 2048 x 2048 for feasible inference | `Analyses/Step_analysis_20260623/selected_1um_input_center2048/bmp` |
| raw full-image ROI Step motion probe | raw selected Step probe using center ROI on full images | `Analyses/Step_analysis_20260623/STEP_MOTION_PROBE_RAW_SUMMARY.md` |
| raw center-crop Step motion probe | raw selected Step probe on the staged center crop | `Analyses/Step_analysis_20260623/STEP_MOTION_PROBE_CENTER2048_RAW_SUMMARY.md` |
| R39 center-crop Step reconstruction package | packaged 80-frame PSF-off R39 Step reconstruction for the center crop | `Analyses/Step_analysis_20260623/r61_step_1um_center2048_recon_package` |
| R39 center-crop Step reconstruction output | copied 80-frame R39 reconstruction output | `Analyses/Step_analysis_20260623/r61_step_1um_center2048_reconstruction_outputs` |
| R39 center-crop Step motion probe | image-only repeat and selected +10 motion probe for R39 | `Analyses/Step_analysis_20260623/STEP_MOTION_PROBE_CENTER2048_R39_SUMMARY.md` |
| raw vs R39 center-crop Step motion probe | combined raw/R39 Step guard table for direct next-round comparison | `Analyses/Step_analysis_20260623/STEP_MOTION_PROBE_CENTER2048_RAW_R39_SUMMARY.md` |
| raw vs R39 Step paths TSV | two-case path list used to generate the combined Step guard table | `Analyses/Step_analysis_20260623/step_center2048_raw_r39_paths.tsv` |
| v14 center-crop Step reconstruction package | packaged 80-frame PSF-off v14 Step reconstruction for the center crop | `Analyses/Step_analysis_20260623/r61_step_1um_center2048_recon_package/02_v14_motion_texture_step_1um_center2048` |
| raw vs R39 vs v14 center-crop Step motion probe | combined raw/R39/v14 Step guard table for direct next-round comparison | `Analyses/Step_analysis_20260623/STEP_MOTION_PROBE_CENTER2048_RAW_R39_V14_SUMMARY.md` |
| raw vs R39 vs v14 Step paths TSV | three-case path list used to generate the combined Step guard table | `Analyses/Step_analysis_20260623/step_center2048_raw_r39_v14_paths.tsv` |
| raw vs R39 vs v14 Step preview | two-position visual preview used to inspect the Step reconstruction appearance | `Analyses/Step_analysis_20260623/step_center2048_raw_r39_v14_preview.png` |
| v14 triple gate summary | combined boundary, 20260603 real motion, and Step gate for v14 | `Analyses/Step_analysis_20260623/triple_gate_v14_boundary_real_step_vs_raw_r39.json` |
| full-size R39 failed attempt | failed full-size R39 Step inference; all frames hit CUDA out-of-memory | `Analyses/Step_analysis_20260623/r61_step_1um_recon_package` |
| v14 center-crop stale failed attempt runtime | earlier v14 Step launch attempt with no valid frames; kept only as a diagnostic record | `Analyses/Step_analysis_20260623/r61_step_1um_center2048_recon_package/_r61_real_sample_runtime_20260623_191526` |

## Step Guard Tooling

| item | role | path |
|---|---|---|
| Step motion probe script | repeat-capture and selected +10 position image-motion measurement | `LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/scripts/probe_step_sequence_motion.py` |
| triple gate script | combines simulated boundary, 20260603 real motion, and Step motion checks | `LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/scripts/score_triple_generalization_gate.py` |
| Step motion probe tests | regression tests for Step pair construction and motion summary | `LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/tests/test_probe_step_sequence_motion.py` |
| triple gate tests | regression tests for the combined gate decision | `LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/tests/test_score_triple_generalization_gate.py` |

## Progress and Code Notes

| item | role | path |
|---|---|---|
| R61 progress note | durable written summary through v14 | `LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/R61_PROGRESS_20260623.md` |
| next-round target prompt | direct instruction for the next long run | `LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/next_round_20260623_v15_step_guard/NEXT_ROUND_TARGET_PROMPT.md` |

## Numbers To Carry Forward

| metric | value |
|---|---:|
| v14 simulated boundary mean | 0.483153 px |
| R39 a970 simulated boundary mean | 0.483705 px |
| v14 simulated boundary gate vs R39 | fail, 5 tiny checks |
| raw 20260603 tail std dy | 0.268818 px |
| reg300 20260603 tail std dy | 0.269661 px |
| R39 a970 20260603 tail std dy | 0.278475 px |
| v14 20260603 tail std dy | 0.276390 px |
| Step same-position repeat median | 0.018823 px |
| Step adjacent 0.1 um median measured motion | 0.085740 px |
| Step selected 1 um median measured motion | 0.742768 px |
| Step center-crop raw same-position repeat median | 0.019576 px |
| Step center-crop raw selected 1 um median measured motion | 0.742768 px |
| Step center-crop R39 same-position repeat median | 0.134328 px |
| Step center-crop R39 selected 1 um median measured motion | 8.025572 px |
| Step center-crop v14 same-position repeat median | 0.133604 px |
| Step center-crop v14 selected 1 um median measured motion | 8.026748 px |
| Step center-crop v14 triple gate | fail: boundary fail, 20260603 real-motion fail, Step stability slightly worse than R39 |
| User-calibrated expected 1 um motion for Step | 8.000000 px |

## Do Not Delete Yet

Do not delete the v11, v13, or v14 validation directories yet. They are negative/partial results, but they explain why the next round must include Step and a stronger real-motion gate.
