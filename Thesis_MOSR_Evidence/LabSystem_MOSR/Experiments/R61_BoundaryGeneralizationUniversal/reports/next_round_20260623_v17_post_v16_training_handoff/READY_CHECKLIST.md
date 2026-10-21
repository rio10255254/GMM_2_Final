# Ready Checklist

Use this before the next run reports any result.

## Before Next Candidate

- [ ] Read `V16_VALIDATION_RESULTS.md`.
- [ ] Keep v16 as a diagnostic baseline, not as a successful thesis result.
- [ ] Target the two remaining small-bias boundary failures first.
- [ ] Protect 20260603 tail stability against raw input, not only against R39.
- [ ] Protect Step step std against R39 and v14.
- [ ] Do not use posthoc per-sample correction.

## Before Validation

- [ ] v16 best checkpoint exists.
- [ ] v16 training log exists.
- [ ] v16 data manifest exists.
- [ ] Step center-crop input has 80 BMP files.
- [ ] R39 Step reference has 80 BMP files.
- [ ] v14 Step reference has 80 BMP files.
- [ ] No old background Python or conda process is still running.

## Simulated Boundary Validation

- [ ] Run diverse phantom validation for v16.
- [ ] Score v16 versus R39.
- [ ] Score v16 versus R8.
- [ ] Compare v16 with v14 overall mean.
- [ ] Check bright, 0 px, 0.5 px, annulus, and ellipse groups explicitly.

## 20260603 Real Sequence

- [ ] Reconstruct all 11 frames with v16.
- [ ] Add v16 to the 20260603 package table.
- [ ] Rerun local motion summary including v16.
- [ ] Compare v16 tail std dy with raw input, R39, and v14.

## Step Sequence

- [ ] Reconstruct all 80 center-crop selected Step frames with v16.
- [ ] Confirm v16 output filenames match the staged input filenames.
- [ ] Build a paths TSV containing raw, R39, v14, and v16.
- [ ] Rerun Step motion probe.
- [ ] Check repeatability and selected-step stability.
- [ ] Check replicate stream 0 and stream 1 separately.

## Final Reporting

- [ ] Run the triple gate.
- [ ] Make one preview image comparing raw, reference, and v16.
- [ ] State whether v16 is positive, negative, or inconclusive.
- [ ] If v16 fails, name the exact failed layer before proposing v17.
- [ ] Confirm no background Python or conda process is left running.
