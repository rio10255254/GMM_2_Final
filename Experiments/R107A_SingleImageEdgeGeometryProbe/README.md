# R107A Single-Image Edge Geometry Probe

R107A is the first probe after returning the research mainline to single-image reconstruction. It is not a formal model and initially performs no neural training.

The probe asks whether a single blurred edge can be made clearer by changing only its transition width while keeping its locally measured center fixed. It operates in local edge-normal coordinates rather than predicting a global contour or a free image residual.

## Why this is different

- R92/R100 represented physical edge behavior but still learned image-space outputs where center, width and intensity could compensate for one another.
- R105A predicted a global signed-distance field and directly rendered it; an incorrect zero set moved the whole contour.
- R107A anchors center to local observed evidence and initially permits only an analytic monotonic width correction. It does not need to understand whether the complete object is a circle, crescent, ring, corner or arbitrary topology.

## First gate

The analytic probe must demonstrate all of the following before any learned model is built:

- narrower, more accurate transition profiles on unseen procedural shapes;
- no systematic shift in boundary center or fitted centroid;
- no dark outline, halo or intensity-range overshoot;
- clear-input identity preservation;
- unchanged known displacement and full/tiled behavior;
- safe behavior on JunHua rings and SEM contour crops.

If the oracle-normal version works but the image-estimated-normal version fails, the next problem is orientation and center estimation. If both fail, the fixed-center width-only hypothesis is rejected and no full R107 training should run.

## Prepared project layout

- `config/experiment.json` contains every data, model, training, inference and selection parameter.
- `data/prepare_dataset.py` creates the 5,000-scene training package and 512-scene fixed validation package.
- `model/r107_model.py` defines the fixed-center local edge parameter model.
- `training/train.py` is the direct training entry that can be opened and run from an editor.
- `inference/run_folder.py` reconstructs one image or a folder with canonical core-only tiling.
- `validation/validate_prepared.py` checks data, finite outputs, fixed-midpoint behavior and full/tile parity.
- `scripts/*.ps1` are short Windows launchers with editable command-line parameters.

## Data preparation

The materialized package contains clear targets, supersampled masks and signed-distance sidecars. Degraded sources are generated deterministically per epoch from the saved clear latent scene, so the package stays compact while training sees many PSF, exposure, halo, ghost and noise conditions.

Run from PowerShell:

    .\scripts\prepare_data.ps1

The source labels are drawn at 8x resolution and downsampled once. The package uses 5,000 training scenes and 512 validation scenes with no group overlap. Real SEM, JunHua and HS100MG pixels are not included.

## Training

Open `training/train.py` and run it directly, or use:

    .\scripts\train.ps1 -Epochs 60 -BatchSize 8 -Workers 4

R107 is scratch-only. The training entry deliberately rejects checkpoint resume or inherited weights. A run lock prevents a second simultaneous R107 trainer.

## Inference

    .\scripts\infer.ps1 -Checkpoint <checkpoint.pth> -InputPath <image-or-folder> -OutputPath <output-folder>

Inference uses one grayscale image at a time, reflected halo and core-only output. The default is a 512-pixel core and 96-pixel halo.

## Validation and smoke test

    .\scripts\validate.ps1
    .\scripts\smoke_test.ps1 -Steps 2

The smoke run is explicitly marked non-formal and writes under `runs/r107_smoke`. Preparing and validating the package does not start the 60-epoch training run.

## Current status

The package is `ready_to_train_repaired`. The complete base data contains 5,000 train scenes and 512 fixed validation scenes. The first formal scratch attempt (`r107_formal_scratch_20260825`) was stopped after its epoch-1 metrics became non-finite; no checkpoint was written and none of its weights may be reused.

The mixed-precision failure was isolated and repaired without changing the fixed-center model contract. A fresh 700-step scratch stability run (`r107_bounded_heads_probe_700`) remained finite past the original step-625 failure point. Its saved checkpoint passed finite-output, fixed-midpoint, clear-input identity and full/tiled parity checks. Diagnostic runs are retained as evidence but are not formal model candidates.

`PREPARED_STATE.json` and `FILE_MANIFEST_SHA256.csv` record readiness, provenance, repair evidence and file hashes. The next formal run must use a new run ID and start from random initialization.
