# R61 Next Round Handoff - post v16 full training

This folder is the clean starting packet for the next MOSR boundary and displacement round.

It does not move large artifacts. Training data, weights, reconstructions, and logs stay in their original locations so existing scripts and reports keep working. This folder tells the next run what each artifact is and what to do next.

## Start Here

1. Read `ONE_SHOT_NEXT_ROUND_TARGET_PROMPT.md`.
2. Use `PREVIOUS_ROUND_ORGANIZED_FILES.md` as the file map for the previous round.
3. Use `V16_FULL_TRAINING_STATUS.md` to see exactly what v16 has and has not proven.
4. Read `V16_VALIDATION_RESULTS.md` for the actual v16 verdict.
5. Use `ONE_SHOT_V17_TARGET_PROMPT_AFTER_V16.md` if starting the next model.
6. Use `READY_CHECKLIST.md` before running validation and before reporting.

## Current State

v16 has been implemented, fully trained for 8 epochs, and validated on the three required evidence layers.

The best v16 checkpoint exists:

`Thesis_MOSR_Evidence/LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r61_motion_texture_stepguard_v16_dualgate_boundary_focus_full_e8_20260623_20260623_200020/weights/best_tradeoff.pth.tar`

The important result:

v16 is not promotable as the final thesis result. Read `V16_VALIDATION_RESULTS.md` before starting another candidate.

It has one useful signal: simulated boundary overall mean improved, and several v14 boundary failure groups were fixed. But all three final gates still fail:

- simulated boundary still fails the 0.0 px and 0.5 px small-bias groups;
- 20260603 real-motion tail stability is still worse than raw input and slightly worse than v14;
- Step selected-motion stability is slightly worse than R39 and v14.

## Carry Forward

The next round can now start a new candidate, but only from the diagnosed v16 failures. Do not restart broadly.

The central thesis guardrail is unchanged: this project is about MOSR precision metrology, displacement stability, and measurement uncertainty after neural reconstruction. A sharper-looking image is not enough.
