# R103 Recoverable Detail Scratch

R103 is an independent scratch-trained microscopy reconstruction experiment. It does not load R102, R61, V42, a teacher, a pseudo-label model, SEM pixels, or real HS100MG structures.

## What changed

- Training observations are generated from the procedural truth through a recoverable local optical forward model.
- Exposure, contrast, gamma, and illumination are applied to both the observation and its label. The model is never asked to guess an unknowable source-only exposure correction.
- Every degraded crop is paired with the exact same clear crop. The clear crop teaches a smooth zero-correction response.
- Feature normalization was removed because the R102 audit showed that it erased subtle local amplitude and detail cues.
- Low-frequency, contour, and texture targets form a non-overlapping residual decomposition.
- Loss weights are fixed. They are not changed from scalar loss values, which were a poor proxy for gradient strength in R102.

## Use

- Start the one authorized full run with `Start_R103_Training.cmd`.
- Open the live monitor with `Open_Training_Monitor.cmd`.
- Edit the documented settings in `config/experiment.json` before the formal run only.
- Run inference after training with `inference/run_inference.py`.

The formal launcher refuses a second formal run and refuses to start without a passed preflight report.
