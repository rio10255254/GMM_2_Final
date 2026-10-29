# R61 Next Round Handoff - v16

This handoff package is the clean starting point for the next long-running MOSR boundary and displacement experiment.

It does not move or duplicate large artifacts. The previous run already produced many images, reconstructions, logs, and summaries in stable locations. Moving them would break existing scripts and reports, so this folder organizes them by index and usage.

## Start Here

1. Read `ONE_SHOT_NEXT_ROUND_TARGET_PROMPT.md`.
2. Use `PREVIOUS_ROUND_ORGANIZED_FILES.md` as the file map for the previous round.
3. Use `READY_CHECKLIST.md` before training, after training, and before reporting.
4. Read `V16_IMPLEMENTATION_STATUS.md` for the new v16 candidate and dataset package that were added after this handoff was first created.

## Completion Standard For The Next Round

The next round is complete only if it produces a new trained candidate and checks it on all three required evidence layers:

- Simulated diverse phantom boundary validation.
- The real 20260603 displacement sequence.
- The Step small-displacement sequence.

Do not call the candidate successful unless it improves or at least protects all three layers. A sharper-looking reconstruction is not enough.

## Current Verdict To Carry Forward

v14 is useful but not thesis-promotable as the final answer.

It slightly improved the simulated boundary overall mean, and it is the best R61-series result so far on the 20260603 real-motion tail stability. But it still fails the strict simulated boundary groups, still does not beat raw input on the 20260603 motion probe, and slightly loses the Step stability comparison against R39.

The Step dataset is now staged and must be used as a guard in the next round. Its physical scale remains suspicious: raw Step motion measures about 0.74 px for the selected +10-position sequence, while the user calibration says 1 um should be 8 px. R39 and v14 reconstructions recover about 8 px on the center crop, so this must be treated carefully before making a physical claim.

## Do Not Delete Yet

Keep all v11, v13, v14, R39, and Step artifacts for now. Several are negative or partial results, but they explain why the next model must be judged by boundary accuracy and displacement stability together.
