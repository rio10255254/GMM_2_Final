# R49_CADAnchorRealGeometry

Lab-system CAD-anchor real-geometry experiment.

R49 tests whether a small amount of real Lab checkboard image data with
CAD-derived sharp targets can correct the rounded-corner failure seen in
R48. The training package keeps the reusable R47/R48 data flow and adds a
small real CAD-anchor slice rather than replacing the whole synthetic mix.

## Current Status

Data generation, package validation, 100-epoch training, reconstruction, and
real checkboard corner validation are complete.

R49 is a negative result. The real CAD-anchor training did not improve the
real `20250605_checkboard` corner geometry. The best R49 median corner shift
was `9.000 px`, worse than both the previous Lab R40 control at `4.243 px`
and the best R48 result at `6.708 px`. It should not be promoted.

Validated during this run:

- CAD-anchor source patches generated from 36 valid real checkboard/CAD pairs
- Training package: 4000 pairs
- Held-out real CAD-anchor validation package: 120 pairs
- Geometry sidecars: present for every packaged source image
- Unit tests: passing
- Dry run: passed
- Smoke training: passed
- Formal training: completed to 100 epochs
- Real checkboard reconstruction: 51 frames each for `best_tradeoff`,
  `best_detail_guarded`, and `latest`
- Real corner validation: failed

## Data

| Package | Role | Pairs |
|---|---|---:|
| `r49_cad_anchor_train_4000` | Training mix: ring, shape, micro/defect, R48 boundary replay, real texture, CAD anchors | 4000 |
| `cad_anchor_val_real` | Held-out CAD-anchor validation package | 120 |

The CAD-anchor label policy uses the CAD GT inside the reliable mask and keeps
the real source image outside the mask. This avoids teaching the model from
untrusted background regions.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/r49_cad_anchor_data.py` | Generate CAD-anchor patches, build packages, validate splits, write geometry sidecars, and create previews. |
| `scripts/launch_r49.py` | Launch Lab R49 training from the Lab R40 tradeoff checkpoint with Lab PSF and geometry sidecars mounted. |

## Verification

The R49 tests are in `tests/` and cover:

- CAD-anchor patch split separation
- masked CAD-label blending
- exact train package composition
- geometry sidecar packaging
- launcher dry-run behavior
- training-role compatible package paths

## Storage Lifecycle

The full R49 history was archived to
`H:\GMM_2_Final_Archive\lab_system\R49_CADAnchorRealGeometry\20260809_full_history`
on 2026-08-10. Thirteen SHA-256 manifests passed before and after the exact
D-drive cleanup. The cleanup removed 62 verified bulky targets and reclaimed
8.7816 GiB of physical D-drive space.

The D-drive copy remains the canonical reading and recovery entry. It keeps the
three reports, package manifests, scripts, tests, training logs and curves,
corner-validation evidence, inference logs, and archive pointers. Restore the
full payload from H and verify it with `Lab_R49_*_20260809.csv` before rerunning
the complete historical package.

R53's data builder references `Training_Data/r49_cad_anchor_source`. Restore
that archived source directory before rebuilding R53.

## Next Step

Do not continue by simply increasing CAD-anchor epochs or ratio. R49 shows that
small masked CAD targets can make the model conservative or unstable on the real
sequence. The next redesign should treat real captured checkboard frames as a
direct validation constraint and should explicitly penalize corner-response
movement, not only edge sharpness.
