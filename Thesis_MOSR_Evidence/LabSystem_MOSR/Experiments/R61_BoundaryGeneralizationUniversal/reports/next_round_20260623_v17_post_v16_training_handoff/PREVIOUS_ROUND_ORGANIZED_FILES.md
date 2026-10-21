# Previous Round Organized File Map

This file organizes the previous round so the next run can start without searching through the whole project.

Large outputs stay in their original folders. This index explains what each item is, why it matters, and how it should be treated.

## A. This Handoff

| item | what it is | status | path |
|---|---|---|---|
| Current handoff folder | Clean post-v16-training packet for the next run | use first | `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R61_BoundaryGeneralizationUniversal\reports\next_round_20260623_v17_post_v16_training_handoff` |
| Previous v16 handoff folder | The packet made before full v16 training finished | keep as prior note | `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R61_BoundaryGeneralizationUniversal\reports\next_round_20260623_v16_handoff` |
| Older v15 target folder | The Step-guard target made before v16 implementation | keep as prior note | `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R61_BoundaryGeneralizationUniversal\reports\next_round_20260623_v15_step_guard` |

## B. v16 Candidate And Code

| item | what it is | status | path |
|---|---|---|---|
| Dataset builder | Defines the v16 Step-like synthetic guard data | keep | `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R61_BoundaryGeneralizationUniversal\scripts\prepare_r61_universal_dataset.py` |
| Candidate launcher | Defines the official v16 candidate and starts from v14 best | keep | `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R61_BoundaryGeneralizationUniversal\scripts\launch_r61.py` |
| Dataset tests | Tests the v16 data role and no-real-Step leakage behavior | keep running | `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R61_BoundaryGeneralizationUniversal\tests\test_prepare_r61_universal_dataset.py` |
| Launcher tests | Tests that the v16 candidate resolves correctly | keep running | `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R61_BoundaryGeneralizationUniversal\tests\test_launch_r61.py` |

## C. v16 Training Data

| item | what it is | status | path |
|---|---|---|---|
| v16 data package | Old data plus camera-texture known-motion and synthetic Step-like guard data | keep as official v16 data | `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Training_Data\r61_universal_boundary_generalization\hs100mg_basler\r61_universal_boundary_train_motion_texture_step_guard_v16` |
| v16 manifest | Machine-readable description of data counts and labels | use for audit | `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Training_Data\r61_universal_boundary_generalization\hs100mg_basler\r61_universal_boundary_train_motion_texture_step_guard_v16\manifest.json` |

Key counts:

- total rows: 20296;
- known-motion pairs: 6400;
- Step-like synthetic guard rows: 3200.

## D. v16 Training Outputs

| item | what it is | status | path |
|---|---|---|---|
| v16 full run folder | Complete 8-epoch training output | use | `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Traing_Progress\training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r61_motion_texture_stepguard_v16_dualgate_boundary_focus_full_e8_20260623_20260623_200020` |
| v16 best checkpoint | Best saved weight from the full v16 run | validate next | `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Traing_Progress\training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r61_motion_texture_stepguard_v16_dualgate_boundary_focus_full_e8_20260623_20260623_200020\weights\best_tradeoff.pth.tar` |
| v16 stdout log | Main 8-epoch training log | keep for audit | `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R61_BoundaryGeneralizationUniversal\reports\training_logs\r61_motion_texture_stepguard_v16_full_e8_20260623_200012.out.log` |
| v16 stderr log | Warning log; only known SciPy MAT warning seen | keep for audit | `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R61_BoundaryGeneralizationUniversal\reports\training_logs\r61_motion_texture_stepguard_v16_full_e8_20260623_200012.err.log` |
| v16 smoke run folder | One-batch proof that v16 loaded and wrote weights before full training | diagnostic only | `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Traing_Progress\training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r61_motion_texture_stepguard_v16_dualgate_boundary_focus_smoke_v16_20260623_20260623_195253` |

## E. v14 Baseline To Compare Against

| item | what it is | status | path |
|---|---|---|---|
| v14 best checkpoint | Immediate predecessor to v16 | keep as comparison | `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Traing_Progress\training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r61_motion_texture_v11base_dualgate_boundary_focus_motiontexture_full_e8_20260623_150217\weights\best_tradeoff.pth.tar` |
| v14 training folder | Full training output folder | keep | `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Traing_Progress\training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r61_motion_texture_v11base_dualgate_boundary_focus_motiontexture_full_e8_20260623_150217` |
| v14 validation folder | Diverse phantom validation for v14 | use as comparison | `D:\GMM_2_Final\R61_motiontexture_dpv96_20260623\diverse_phantom_validation_20260623_164241` |

Key v14 result:

- v14 slightly improved the overall simulated boundary mean versus R39.
- v14 still failed five strict groups: bright, 0 px bias, 0.5 px bias, annulus, ellipse.

## F. 20260603 Real Sequence Evidence

| item | what it is | status | path |
|---|---|---|---|
| 20260603 package | Existing package for raw and reconstructed 20260603 cases | use | `D:\GMM_2_Final\Reconstruct_Progress\20260603_external_gmf_prepare` |
| v14 20260603 case | v14 reconstruction of the 11-frame real sequence | compare | `D:\GMM_2_Final\Reconstruct_Progress\20260603_external_gmf_prepare\23_r61_motion_texture_v11base_full_e8_best` |
| v14 motion summary | Local-motion summary including v14 | compare | `D:\GMM_2_Final\Reconstruct_Progress\20260603_external_gmf_prepare\local_motion_probe_summary_after_r61_motiontexture_full_e8.json` |

Key values:

- raw tail std dy: 0.268818 px;
- R39 tail std dy: 0.278475 px;
- v14 tail std dy: 0.276390 px.

## G. Step Evidence

| item | what it is | status | path |
|---|---|---|---|
| Step source images | Original Step capture folder with 788 BMP files | source of truth | `D:\GMM_2_Final\Step` |
| Step selection report | Explains selected 1 um sequence | use | `D:\GMM_2_Final\Step_analysis_20260623\STEP_1UM_SELECTION_REPORT.md` |
| Selected center-crop input | 80 selected input images cropped to center 2048 x 2048 | use for v16 inference | `D:\GMM_2_Final\Step_analysis_20260623\selected_1um_input_center2048\bmp` |
| R39 center-crop Step output | 80-frame R39 Step reconstruction | strong reference | `D:\GMM_2_Final\Step_analysis_20260623\r61_step_1um_center2048_recon_package\01_r39_a970_step_1um_center2048\bmp` |
| v14 center-crop Step output | 80-frame v14 Step reconstruction | compare | `D:\GMM_2_Final\Step_analysis_20260623\r61_step_1um_center2048_recon_package\02_v14_motion_texture_step_1um_center2048\bmp` |
| Step raw/R39/v14 summary | Current Step motion summary before v16 | compare | `D:\GMM_2_Final\Step_analysis_20260623\STEP_MOTION_PROBE_CENTER2048_RAW_R39_V14_SUMMARY.md` |
| Step raw/R39/v14 preview | Visual preview of raw, R39, and v14 | inspect | `D:\GMM_2_Final\Step_analysis_20260623\step_center2048_raw_r39_v14_preview.png` |
| v14 triple gate | Combined verdict for v14 | compare | `D:\GMM_2_Final\Step_analysis_20260623\triple_gate_v14_boundary_real_step_vs_raw_r39.json` |

Key values:

- raw repeat median: 0.019576 px;
- raw selected +10 median motion: 0.742768 px;
- R39 repeat median: 0.134328 px;
- R39 selected +10 median motion: 8.025572 px;
- v14 repeat median: 0.133604 px;
- v14 selected +10 median motion: 8.026748 px;
- user-calibrated expected 1 um motion: 8.000000 px.

Important caution:

Raw Step and reconstructed Step do not currently agree on physical scale. Do not make a physical 1 um accuracy claim until this mismatch is explained.

## H. Validation Tools To Use Next

| item | what it does | path |
|---|---|---|
| Diverse phantom validation | Reconstructs and measures simulated boundary cases | `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R61_BoundaryGeneralizationUniversal\scripts\run_diverse_phantom_validation.py` |
| Boundary gate | Scores candidate boundary metrics against a baseline | `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R61_BoundaryGeneralizationUniversal\scripts\score_generalization_gate.py` |
| Real sequence package | Reconstructs and packages 20260603 cases | `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R61_BoundaryGeneralizationUniversal\scripts\prepare_real_sample_gmf_package.py` |
| Step motion probe | Measures repeat and selected-step motion on Step cases | `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R61_BoundaryGeneralizationUniversal\scripts\probe_step_sequence_motion.py` |
| Triple gate | Combines boundary, 20260603, and Step verdicts | `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R61_BoundaryGeneralizationUniversal\scripts\score_triple_generalization_gate.py` |

## I. Do Not Delete Yet

Do not delete v11, v13, v14, v16 smoke, R39, or Step artifacts yet.

Some are negative or partial results, but they explain why the next result must be judged by boundary accuracy and displacement stability together.

