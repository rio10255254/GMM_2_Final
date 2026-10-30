# R57 Pilot Training Status

## Status

R57 has a working experiment package, generated data, training launcher, CD
measurement tool, and CD gate. The first short training runs completed, but no
R57 checkpoint is adoptable yet because the 100MG CD gate still fails against
the original image.

R57.1 added asymmetric CD-correction anchors to teach via expansion and pillar
shrinkage directly. The data generation bug found during the first R57.1 run was
fixed: synthetic source and label anchors now share the same circle centers and
only differ in radius. After regenerating the data and retraining, R57.1 still
failed the CD gate and is explicitly not adopted.

## Data

- Mixed package: `r57_hs100mg_r55_finetune_train`
- Base R55 pairs: 6000
- HS-100MG / Basler anchor pairs: 2048
- Total pairs: 8048
- Geometry sidecars: 8048 boundary, 8048 centerline, 8048 distance maps

## CD Results

All values below are absolute radius error versus SEM, in nm.

| Candidate | Via | Pillar | Mean | Gate |
| --- | ---: | ---: | ---: | --- |
| Original image | 66.13 | 11.04 | 38.59 | Reference |
| R55 PSF-off | 80.28 | 43.41 | 61.84 | Fail |
| R55 PSF-on | 81.59 | 46.55 | 64.07 | Fail |
| R57 mixed pilot best | 84.01 | 44.27 | 64.14 | Fail |
| R57 anchor-focus latest | 72.88 | 25.34 | 49.11 | Fail |
| R57 anchor-focus then mixed best | 75.02 | 33.38 | 54.20 | Fail |
| R57.1 asymmetric CD latest | 106.97 | 74.17 | 90.57 | Fail |

## Readout

The first mixed pilot did not correct the CD bias. The anchor-focus run moved in
the right direction: compared with R55 PSF-off, mean CD error dropped from 61.84
nm to 49.11 nm, and pillar error dropped from 43.41 nm to 25.34 nm. It still did
not beat the original image, so it is not acceptable as a thesis candidate yet.

The mixed recovery run after anchor-focus partially undid the improvement.

The R57.1 asymmetric CD run overshot in the wrong direction on both feature
types: via error increased from 66.13 nm in the original image to 106.97 nm, and
pillar error increased from 11.04 nm to 74.17 nm. This rejects the simple
"measured raw-bias to SEM label" anchor strategy as a candidate model. The best
current exploratory model remains `R57 anchor-focus latest`, but it is still not
good enough for thesis adoption because it does not beat the original image.

Next training should keep the R57 anchor-focus recipe as the starting point, but
the CD correction must be weaker and measured as a validation objective instead
of being injected as a full-radius source/label jump.

## Verification

- R57 unit tests: 9 passed after adding R57.1 coverage.
- Dataset generation: completed.
- Launcher dry-run: completed.
- Smoke training: completed.
- Three pilot/recovery training runs: completed.
- R57.1 aligned pilot training: completed.
- R57.1 reconstruction, CD measurement, and gate report: completed.
