# LabSystem_MOSR Manifest

Last updated: 2026-06-14

## PSF Calibration

| Item | Status | Location |
|---|---|---|
| Raw calibration captures | archived | `psf_calibration/raw/20250605_PSF_Calibration/` |
| Project-standard Whole-FOV fitter copy | staged | `psf_calibration/scripts/standard_wholefov/` |
| Superseded full-frame staging | archived | `psf_calibration/archive/20250608_psf_cleanup/inputs/20250605_standard_wholefov_fullframe_blocked/` |
| Inner-circle ROI GT | prepared | `psf_calibration/inputs/20250605_inner_circle_roi/GT/LAB_INNER_CIRCLE_GT_901.bmp` |
| Inner-circle ROI images | prepared | `psf_calibration/inputs/20250605_inner_circle_roi/measured/` |
| Inner-circle detection evidence | active input support | `psf_calibration/inputs/20250605_inner_circle_roi/detection/` |
| Superseded first BADS fit | archived comparison evidence | `psf_calibration/archive/20250608_psf_cleanup/results/20250605_inner_circle_roi_standard_fit_superseded_by_fine/` |
| Fine pre-alignment BADS PSF candidate | validated; selected as BADS candidate | `psf_calibration/results/20250605_inner_circle_roi_fine_prealign_fit/` |
| Current PSF validation package | validated | `psf_calibration/results/20250605_inner_circle_roi_fine_prealign_validation/` |
| Fine pre-alignment comparison report | updated | `psf_calibration/reports/FINE_PREALIGN_COMPARISON_20250608.md` |
| Lab Training_Data root | stage 1-33 + R39/R40 complete | `Training_Data/` |
| Lab clean-GT generator | copied from main project; lab stage/seed controls added | `Training_Data/Data_Simulaion.py` |
| Lab PSF convolution script | copied from main project; lab PSF path and Gaussian control added | `Training_Data/PSF_Convolution.py` |
| Lab data generation config | stage 1-33 + R39/R40 complete | `Training_Data/configs/lab_data_generation_20250605.json` |
| Lab first sequence report | completed | `Training_Data/reports/FIRST_SEQUENCE_GENERATION_20250608.md` |
| Lab first sequence preview | completed | `Training_Data/reports/stage25_26_first_generation_preview.png` |
| Lab full data foundation report | completed | `Training_Data/reports/LAB_TRAINING_DATA_STAGE01_33_20250608.md` |
| Lab full data foundation preview | completed | `Training_Data/reports/lab_training_data_stage01_33_preview.png` |
| Lab ring replay package | completed | `Training_Data/tra_src_ring/` + `Training_Data/tra_lbl_ring/` |
| Lab R39 data packages | completed | `Training_Data/r39_shape_generalization/` |
| Lab R40 data packages | completed | `Training_Data/r40_microscopy_feature_coverage/` |
| R39 shape package builder | copied from main project | `Experiments/R39_ShapeGeneralization/scripts/r39_shape_data.py` |
| R40 microscopy package builder | copied from main project | `Experiments/R40_MicroscopyFeatureCoverage/scripts/r40_micro_data.py` |
| Lab R39 training launcher | tested; dry-run + smoke + 25-epoch bootstrap + 100-epoch formal run complete | `Experiments/R39_ShapeGeneralization/scripts/launch_r39.py` |
| Lab R40 training launcher | tested; dry-run + smoke + 25-epoch bootstrap + 100-epoch formal run complete | `Experiments/R40_MicroscopyFeatureCoverage/scripts/launch_r40.py` |
| Lab training bootstrap report | completed | `Experiments/reports/LAB_TRAINING_BOOTSTRAP_20250608.md` |
| Lab formal 100-epoch training report | completed | `Experiments/reports/LAB_FORMAL_TRAINING_100E_20260609.md` |
| Lab R39 formal 100-epoch run | completed | `Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r39_shape_mix_safe_20260609_173931/` |
| Lab R40 formal 100-epoch run | completed | `Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r40_micro_capacity_combo_20260609_185153/` |
| Lab checkpoint compatibility cache | created | `Traing_Progress/_checkpoint_cache/` |
| Lab inference script | copied from main project; Lab defaults added | `scripts/GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py` |
| Lab checkboard external GMF package | completed; raw + R39/R40 latest + R39/R40 tradeoff cases verified and scored | `Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/` |
| Lab checkboard external GMF report | completed; R39 tradeoff best on raw step_std | `Experiments/reports/LAB_CHECKBOARD_EXTERNAL_GMF_20260611.md` |
| Lab checkboard GMF diagnostic report | completed; corner-geometry target mismatch now identified as primary visual limiter | `Experiments/reports/LAB_CHECKBOARD_GMF_DIAGNOSTIC_20260611.md` |
| Lab checkboard root-cause deep probe | completed; corner validation shifts next step to checkboard/corner data guard | `Experiments/reports/LAB_GMF_ROOT_CAUSE_DEEP_PROBE_20260611.md` |
| Lab checkboard corner geometry validation | completed; 51 frames / 358 raw corners checked | `Experiments/reports/LAB_CHECKBOARD_CORNER_VALIDATION_20260611.md` |
| Lab checkboard corner validation artifacts | completed; metrics, plot, and contact sheet generated | `Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation/` |
| Lab R46 checkboard/corner data extension | completed; clean/BADS/Gaussian data + train/val packages built | `Training_Data/reports/LAB_R46_CHECKBOARD_CORNER_DATA_20260612.md` |
| Lab R46 checkboard/corner builder | tested | `Experiments/R46_CornerAwareFineTune/scripts/r46_corner_data.py` |
| Lab R46 conservative training launcher | dry-run + smoke + 25-epoch formal training verified | `Experiments/R46_CornerAwareFineTune/scripts/launch_r46.py` |
| Lab R46 smoke run | completed; 1 epoch / 1 train batch | `Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r46_checkboard_corner_r39_latest_20260612_111237/` |
| Lab R46 formal training report | completed; reconstruction validation completed and did not pass | `Experiments/R46_CornerAwareFineTune/reports/R46_RESULTS_20260612.md` |
| Lab R46 formal training run | completed; final + tradeoff + detail-guarded checkpoints produced | `Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r46_checkboard_corner_r39_latest_20260612_112100/` |
| Lab R46 checkboard reconstruction outputs | completed; 3 R46 cases, 51 frames each | `Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/reconstruct_progress_*_20260612_112100/` |
| Lab R46 external GMF cases | completed; ready for external tool if needed | `Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/gmf_cases/lab_r46_*/` |
| Lab R46 real-corner validation | completed; R46 did not solve rounded-corner issue | `Experiments/reports/LAB_R46_CHECKBOARD_CORNER_VALIDATION_20260612.md` |
| Lab R47 realistic boundary data expansion | completed; 4000-pair train package + 800-pair held-out validation package built | `Training_Data/r47_realistic_boundary_generalization/` |
| Lab R47 realistic boundary builder | tested | `Experiments/R47_RealisticBoundaryGeneralization/scripts/r47_realistic_boundary_data.py` |
| Lab R47 realistic boundary data report | completed | `Training_Data/reports/LAB_R47_REALISTIC_BOUNDARY_DATA_20260612.md` |
| Lab R47 formal 200-epoch training report | completed | `Experiments/R47_RealisticBoundaryGeneralization/reports/R47_RESULTS_20260613.md` |
| Lab R47 formal 200-epoch run | completed; epoch 33 best_tradeoff and epoch 200 latest checkpoints produced | `Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r47_realistic_boundary_r39_latest_20260612_171140/` |
| Lab R47 checkboard reconstruction outputs | completed; epoch 33 and epoch 200 cases, 51 frames each | `Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/reconstruct_progress_*_20260612_171140/` |
| Lab R47 external GMF cases | prepared; filenames and dimensions verified, external scores pending | `Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/gmf_cases/lab_r47_*/` |
| Lab R47 real-corner validation | completed; R47 did not solve rounded-corner issue | `Experiments/R47_RealisticBoundaryGeneralization/reports/R47_CHECKBOARD_VALIDATION_20260613.md` |
| Lab R48 real-corner data expansion | completed; 6000-pair train package + 1200-pair held-out package with geometry sidecars built | `Training_Data/r48_real_corner_transfer/` |
| Lab R48 real-corner builder | tested | `Experiments/R48_RealCornerTransfer/scripts/r48_real_corner_data.py` |
| Lab R48 real-corner training launcher | dry-run + smoke + geometry-smoke verified | `Experiments/R48_RealCornerTransfer/scripts/launch_r48.py` |
| Lab R48 real-corner data report | completed | `Training_Data/reports/LAB_R48_REAL_CORNER_DATA_20260613.md` |
| Lab R48 formal 200-epoch R39-start run | completed to epoch 120, then resumed | `Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r48_real_corner_r39_latest_20260613_163644/` |
| Lab R48 formal resume run | completed to epoch 200 | `Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r48_real_corner_r39_latest_resume_e120_to200_20260613_235726/` |
| Lab R48 checkboard reconstruction outputs | completed; 3 R48 cases, 51 frames each | `Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/reconstruct_progress_*_20260613_*/` |
| Lab R48 external GMF cases | prepared; filenames and dimensions verified | `Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/gmf_cases/lab_r48_*/` |
| Lab R48 formal training and validation report | completed; R48 did not pass | `Experiments/R48_RealCornerTransfer/reports/R48_RESULTS_20260614.md` |
| Lab R48 real-corner validation | completed; R48 worsened real corner metrics | `Experiments/R48_RealCornerTransfer/reports/R48_CHECKBOARD_VALIDATION_20260613.md` |
| Lab R50 PSF/degradation diagnosis | completed; BADS usable but too soft as the only checkboard-corner blur truth | `Experiments/R50_PSFControlDiagnosis/reports/R50_RESULTS.md` |
| Lab R50 PSF-control artifacts | completed; weak-BADS controls, metrics, chart, and contact sheet generated | `Experiments/R50_PSFControlDiagnosis/results/psf_control_diagnosis/` |
| Lab R51 blur-source probe packages | completed; Gaussian, weak-BADS, mixed-PSF train packages plus held-out mixed validation built | `Training_Data/r51_blur_source_probe/` |
| Lab R51 blur-source probe launcher | tested; dry-run, smoke, and three short probe runs completed | `Experiments/R51_BlurSourceProbe/scripts/launch_r51.py` |
| Lab R51 short probe training runs | completed; Gaussian, weak-BADS, and mixed-PSF checkpoints produced | `Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r51_*_short_e012_b080_20260614_*/` |
| Lab R51 checkboard reconstruction outputs | completed; 6 R51 cases, 51 frames each | `Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/r51_reconstruction_outputs/` |
| Lab R51 blur-source results report | completed; directional improvement but not promoted | `Experiments/R51_BlurSourceProbe/reports/R51_RESULTS.md` |
| Lab R51 real-corner validation | completed; mixed-PSF improved median shift but failed large-shift stability | `Experiments/R51_BlurSourceProbe/reports/R51_CHECKBOARD_VALIDATION.md` |
| Old lab_data_generation folder | legacy planning note only | `lab_data_generation/` |
| Edge-derived Gaussian estimate | archived exploratory only | `psf_calibration/archive/20250608_psf_cleanup/results/20250605_edge_psf_exploratory/` |
| PSF cleanup archive index | updated | `psf_calibration/archive/20250608_psf_cleanup/ARCHIVE_INDEX.md` |
| Human summary | updated | `psf_calibration/reports/PSF_CALIBRATION_20250605_SUMMARY.md` |

## Next Planned Blocks

These are placeholders for later phases and are not active yet:

- Lab data generation: stage 1-33 clean GT, BADS PSF, Gaussian control, ring replay, R39/R40 packages, R46 corner package, R47 realistic boundary package, R48 real-corner geometry package, R50 weak-BADS diagnostic controls, and R51 blur-source probe packages completed
- Lab model training: R39/R40 bootstrap and formal 100-epoch runs completed; R46 first formal 25-epoch fine-tune completed; R47 full 200-epoch run completed; R48 formal 200-epoch R39-start run completed; R51 three short blur-source probe runs completed
- Lab R48 result: reconstruction and real-corner validation completed; R48 failed and should not be promoted
- Lab R51 result: mixed-PSF reduced median corner shift versus R40, but the large-shift corner rate stayed worse; R51 is directional evidence only and should not be promoted
- Lab next work: keep the mixed-PSF direction, but add a real-corner stability guard before any next long formal Lab run
