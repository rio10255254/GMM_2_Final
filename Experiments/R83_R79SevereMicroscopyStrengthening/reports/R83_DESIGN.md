# R83 Design

## Hypothesis

R79's strong SEM and motion behavior can be retained if only its final reconstruction layers are fine-tuned, while the data distribution is corrected for severe blur, noise, low contrast, halo, and repeated local boundary loss.

## Data correction

- 5,120 procedural pairs, grouped by geometry before splitting.
- 1,280 severe boundary pairs: four recoverable renderings and four deliberately ambiguous renderings per geometry.
- Recoverable renderings keep the 8x-drawn clean target.
- Ambiguous renderings use a recorded conservative target so invisible boundaries are not rewarded as hallucinations.
- 3,040 broad, non-circular, dense, and multiscale replay pairs plus 800 exact/near-identity guards prevent forgetting.
- No measured contour, sample dimension, real microscope pixel, SEM pixel, legacy pair, teacher output, or pseudo-label is allowed.

## Model update

- Start from an exact copy of R79 epoch-23 EMA parameters.
- Reset optimizer and epoch.
- Save the untouched epoch-zero R79 state as an eligible fallback before the first update; R83 is not allowed to force a worse fine-tuned state.
- Pilot two bounded choices: boundary adapter only, or boundary adapter plus final reconstruction tail.
- Do not enable the global quality gate unless the locked preflight blend screen shows it can help R74 without harming SEM.
- Formal fine-tune is limited to 30 epochs with validation every two epochs because R79 already showed real-generalization deterioration during long training.

## Evidence eligibility

- R73 and R74 are developmental for R83 because their failure modes informed this design.
- The pre-generated 384-pair locked holdout, the frozen six real-motion sequences, and the verified 36-pillar SEM comparison are the clean confirmation surfaces.
- No post-hoc image exclusions or cross-suite averaging are permitted.
