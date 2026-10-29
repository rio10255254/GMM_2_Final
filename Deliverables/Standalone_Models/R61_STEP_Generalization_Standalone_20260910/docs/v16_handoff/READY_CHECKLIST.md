# Ready Checklist For The Next Round

Use this checklist before, during, and after the next long-running experiment.

## Before Changing Anything

- Confirm the v14 best checkpoint exists.
- Confirm Step source has 788 BMP files.
- Confirm Step center-crop selected input has 80 BMP files.
- Confirm R39 and v14 center-crop Step outputs each have 80 BMP files.
- Run the R61 tests before modifying training or validation code.
- Check that no stale Python, conda, or inference processes are running.

## Before Training

- State which old data is being kept.
- State what new guard is being added.
- Confirm no same-sample posthoc correction is being introduced.
- Confirm real Step data is used as validation first, not as answer leakage.
- Confirm PSF-off or weak-PSF-off is the primary validation setting.

## During Training

- Save the training command or launcher settings.
- Save stdout and stderr logs.
- Save the dataset package name.
- Save the best checkpoint path.
- Watch for a model that gets sharper but starts failing motion checks.

## After Training

- Run simulated diverse phantom validation.
- Run 20260603 real-sequence reconstruction and motion summary.
- Run Step center-crop reconstruction and motion summary.
- Run the triple gate.
- Make one preview image with raw, R39 or v14, and the new candidate.
- Update the R61 progress note.
- Check for and clean up any lingering Python, conda, or inference processes.

## Reporting Rule

Report the result as one of three states:

- Positive: all three layers support the candidate.
- Inconclusive: one layer improves but another layer fails or is suspicious.
- Negative: the model looks sharper but boundary or displacement checks get worse.

Do not present an inconclusive or negative candidate as thesis-ready.

