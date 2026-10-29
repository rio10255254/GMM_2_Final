# One-Shot Target Prompt For The Next Run

Use this whole file as the instruction for the next agent or resumed run.

## Mission

Continue from the trained v16 R61 candidate and decide whether it actually improves MOSR boundary reconstruction and displacement measurement stability.

Do not start by designing another model. First validate the v16 full-training checkpoint across all three evidence layers. If v16 fails, diagnose which layer failed and only then design the next candidate.

## Current Candidate

Candidate name:

`r61_motion_texture_stepguard_v16_dualgate_boundary_focus`

Best v16 checkpoint:

`Thesis_MOSR_Evidence/LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r61_motion_texture_stepguard_v16_dualgate_boundary_focus_full_e8_20260623_20260623_200020/weights/best_tradeoff.pth.tar`

Training log:

`Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/training_logs/r61_motion_texture_stepguard_v16_full_e8_20260623_200012.out.log`

Dataset package:

`Thesis_MOSR_Evidence/LabSystem_MOSR/Training_Data/r61_universal_boundary_generalization/hs100mg_basler/r61_universal_boundary_train_motion_texture_step_guard_v16`

## Non-Negotiable Rules

- Do not use after-the-fact sample-specific correction.
- Do not "fix" measurements by drawing, shifting, or calibrating outputs after inference.
- Do not promote a candidate only because it works on the current sample.
- Do not make PSF-on the main result. Primary validation must be PSF-off or weak-PSF-off.
- Do not discard useful old training data.
- Do not call v16 successful unless simulated boundary, 20260603 real motion, and Step checks all support it.

## Known v16 Training Facts

The v16 dataset reuses old data and adds a synthetic Step-like guard. It does not train on real Step pixels or real Step labels.

Dataset size:

- total pairs: 20296;
- known-motion pairs: 6400;
- Step-like synthetic guard rows: 3200.

Full training reached epoch 8 and wrote `best_tradeoff.pth.tar`.

Best training summary from the log:

- best epoch: 8;
- validation reconstruction loss: 0.005981;
- validation SSIM: 0.9437;
- tradeoff score: 136.4300.

This is only training evidence. It is not the final answer.

## Required Validation A - Simulated Diverse Phantom Boundary

Purpose: prove the candidate is not just learning the current sample.

Run the 96-case diverse phantom validation with v16 weights:

```powershell
python .\LabSystem_MOSR\Experiments\R61_BoundaryGeneralizationUniversal\scripts\run_diverse_phantom_validation.py `
  --weights "Thesis_MOSR_Evidence/LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r61_motion_texture_stepguard_v16_dualgate_boundary_focus_full_e8_20260623_20260623_200020/weights/best_tradeoff.pth.tar" `
  --output-root "R61_stepguard_v16_dpv96_20260623" `
  --device cuda:0
```

Then score v16 against R39 and R8 using `score_generalization_gate.py`.

Important: do not treat the v14 `boundary_metrics.csv` as the R39 or R8 baseline. It is the v14 candidate table. Locate the real R39 and R8 baseline metric tables from the previous gate run or rerun their diverse phantom validation if needed, then compare v16 against those tables.

Use the existing v14 validation folder as the comparison reference:

`R61_motiontexture_dpv96_20260623/diverse_phantom_validation_20260623_164241`

Acceptance checks:

- overall mean must not be worse than v14;
- bright-boundary group must not regress versus R39;
- 0 px and 0.5 px small-bias groups must not regress versus R39;
- annulus and ellipse groups must not regress versus R39;
- report group failures, not only the overall mean.

## Required Validation B - 20260603 Real Sequence

Purpose: test whether v16 helps real displacement stability.

Prepare a new v16 20260603 reconstruction case:

```powershell
python .\LabSystem_MOSR\Experiments\R61_BoundaryGeneralizationUniversal\scripts\prepare_real_sample_gmf_package.py `
  --weights "Thesis_MOSR_Evidence/LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r61_motion_texture_stepguard_v16_dualgate_boundary_focus_full_e8_20260623_20260623_200020/weights/best_tradeoff.pth.tar" `
  --case-name "24_r61_motion_texture_stepguard_v16_full_e8_best" `
  --role "r61_motion_texture_stepguard_v16_full_e8_best" `
  --device cuda:0 `
  --note "v16 Step-guard full 8 epoch best checkpoint, PSF-off or weak-PSF-off reconstruction for 20260603 motion validation."
```

Then rerun the local motion probe summary so the new case is compared with raw input, R39, and v14.

Use the current v14 summary as the comparison reference:

`Analyses/Reconstruct_Progress/20260603_external_gmf_prepare/local_motion_probe_summary_after_r61_motiontexture_full_e8.json`

Acceptance checks:

- v16 tail std dy must not be worse than raw input;
- v16 tail std dy must beat v14 before claiming progress;
- motion response must not collapse relative to v14;
- if visual sharpness improves but this motion check worsens, the problem is not solved.

## Required Validation C - Step Selected 1 um Sequence

Purpose: test whether v16 preserves small-displacement behavior on a different capture set.

Source images:

`Step`

Staged center-crop input:

`Analyses/Step_analysis_20260623/selected_1um_input_center2048/bmp`

Package folder to keep outputs comparable:

`Analyses/Step_analysis_20260623/r61_step_1um_center2048_recon_package`

Use the same inference behavior as the real-sample package: all BMPs, PSF from argument, checkpoint PSF ignored, weak PSF disabled, physical alpha zero.

Recommended case name:

`03_v16_stepguard_step_1um_center2048`

After inference, make a new paths TSV that includes:

- raw center-crop input;
- R39 center-crop reconstruction;
- v14 center-crop reconstruction;
- v16 center-crop reconstruction.

Then run:

```powershell
python .\LabSystem_MOSR\Experiments\R61_BoundaryGeneralizationUniversal\scripts\probe_step_sequence_motion.py `
  --paths-tsv "Analyses/Step_analysis_20260623/step_center2048_raw_r39_v14_v16_paths.tsv" `
  --selected-manifest "Analyses/Step_analysis_20260623/selected_1um_positions.csv" `
  --output-json "Analyses/Step_analysis_20260623/step_motion_probe_center2048_raw_r39_v14_v16_summary.json" `
  --output-csv "Analyses/Step_analysis_20260623/step_motion_probe_center2048_raw_r39_v14_v16_pairs.csv" `
  --output-md "Analyses/Step_analysis_20260623/STEP_MOTION_PROBE_CENTER2048_RAW_R39_V14_V16_SUMMARY.md"
```

Acceptance checks:

- check same-position repeatability;
- check selected +10-position step stability;
- check replicate stream 0 and replicate stream 1 separately;
- compare raw, R39, v14, and v16;
- do not claim physical 1 um accuracy until the raw-versus-reconstruction Step scale mismatch is explained.

## Required Final Gate

After the three validation layers are complete, run the combined gate:

```powershell
python .\LabSystem_MOSR\Experiments\R61_BoundaryGeneralizationUniversal\scripts\score_triple_generalization_gate.py `
  --boundary-gate-json "<v16 gate versus R39 json>" `
  --real-motion-summary-json "Analyses/Reconstruct_Progress/20260603_external_gmf_prepare/local_motion_probe_summary_after_r61_stepguard_v16_full_e8.json" `
  --real-motion-baseline-case "raw_input" `
  --real-motion-candidate-case "24_r61_motion_texture_stepguard_v16_full_e8_best" `
  --step-summary-json "Analyses/Step_analysis_20260623/step_motion_probe_center2048_raw_r39_v14_v16_summary.json" `
  --step-baseline-case "01_r39_a970_step_1um_center2048" `
  --step-candidate-case "03_v16_stepguard_step_1um_center2048" `
  --output-json "Analyses/Step_analysis_20260623/triple_gate_v16_boundary_real_step_vs_raw_r39.json" `
  --no-fail-exit
```

If exact case names differ in the generated JSON, inspect the summary first and use the actual names.

## Verdict Rules

Call v16 positive only if all are true:

- strict simulated boundary groups do not regress;
- 20260603 real-motion tail stability improves or is protected;
- Step repeatability and selected-step stability improve or are protected;
- validation is PSF-off or weak-PSF-off;
- no posthoc per-sample calibration is used.

Call v16 inconclusive if it improves one layer but hurts another.

Call v16 negative if it mainly makes images sharper while boundary or displacement checks get worse.

## Required Outputs

The next run must produce:

- v16 diverse phantom validation folder;
- v16 gate versus R39 and R8;
- v16 20260603 reconstruction folder and motion summary;
- v16 Step reconstruction folder and motion summary;
- v16 triple-gate summary;
- one preview image comparing raw, R39 or v14, and v16;
- one plain-language progress note explaining whether v16 is positive, negative, or inconclusive;
- a process cleanup check showing no background Python or conda process was left running.

## If v16 Fails

Do not patch the measurement after inference.

Diagnose the failure layer:

- If simulated boundary fails: add targeted synthetic pressure for the failing group.
- If 20260603 fails: tune motion-consistency pressure without using sample-specific correction.
- If Step fails: add more synthetic Step-like and repeat-capture guards, still without training on real Step answers unless a clean holdout split is created.

Only start v17 after this diagnosis.
