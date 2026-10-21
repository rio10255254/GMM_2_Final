# R51_BlurSourceProbe

Lab-system blur-source training probe.

R51 tests the immediate next question from R50: if the formal BADS blur is too
soft as the only checkboard-corner blur truth, does a short Gaussian,
weak-BADS, or mixed-PSF probe improve the real Lab checkboard corners?

## Current Status

Data generation, split validation, smoke training, short probe training,
reconstruction, and real checkboard corner validation are complete.

R51 is directional evidence, not a promoted model. The best R51 result was the
mixed-PSF `best_tradeoff` checkpoint. It improved the median real-corner shift
from the Lab R40 control's `4.243 px` to `2.828 px`, but it still increased the
large-shift corner rate from `24.581%` to `36.872%`. It should not replace R40
as the current Lab control.

Validated during this run:

- Three training probes: Gaussian, weak-BADS alpha 0.50, and mixed PSF
- Training packages: 1550 pairs per probe
- Held-out mixed corner validation package: 100 pairs
- Unit tests: passing
- Dry run: passed
- Smoke training: passed
- Short probe training: completed for all three candidates
- Real checkboard reconstruction: 51 frames for each R51 checkpoint case
- Real corner validation: improved median shift but did not pass the stability gate

## Data

| Package | Role | Pairs |
|---|---|---:|
| `r51_gaussian_corner_probe` | Ring/shape/micro replay plus Gaussian corner blur | 1550 |
| `r51_weak_bads_corner_probe` | Ring/shape/micro replay plus weak-BADS corner blur | 1550 |
| `r51_mixed_psf_corner_probe` | Ring/shape/micro replay plus formal-BADS, Gaussian, and weak-BADS corner blur | 1550 |
| `r51_mixed_corner_val` | Held-out mixed corner validation | 100 |

## Scripts

| Script | Purpose |
|---|---|
| `scripts/r51_blur_source_data.py` | Build the three blur-source training packages and the held-out validation package. |
| `scripts/launch_r51.py` | Launch short Lab R51 training probes from the Lab R40 tradeoff checkpoint. |
| `scripts/run_r51_checkboard_reconstruction.py` | Reconstruct the real `20250605_checkboard` sequence for the R51 checkpoints and package GMF-ready cases. |

## Verification

The R51 tests are in `tests/` and cover:

- Package composition and blur-source separation
- Train/validation split validation
- Launcher dry-run behavior
- Reconstruction case discovery and output packaging

## Next Step

Do not promote R51 or simply extend this exact short run. The useful result is
that mixed/weak blur sources can reduce the typical corner shift, but the model
still produces too many unstable corners. The next round should keep the
mixed-PSF direction but add an explicit real-corner stability constraint or
checkpoint-selection gate before committing to a long formal run.
