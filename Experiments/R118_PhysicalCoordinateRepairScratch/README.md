# R118 physical-coordinate repair

This folder contains the revised design, self-contained training/inference
programs, repaired data, tests, and development experiments. Original R117
code, weights, and diagnostic records remain untouched.

## Start here

- **Next-design work starts at [NEXT_STEPS.md](NEXT_STEPS.md).** It is prepared,
  not implemented or trained. The checker is read-only. The following R118
  training entry does NOT launch the proposed sequence/geometry design.
- Open **Train.py** in the Python editor and press Run to start one new,
  independent 42-epoch formal run after readiness validation.
- Edit **config/experiment.json** to adjust data noise, model capacity, batch
  size, learning rates, and objective weights. The training program reads these
  values directly. A new run always creates random model weights.
- Set the three paths at the top of **Infer.py** and press Run to reconstruct
  images. Existing images and output files are never overwritten.
- Run **scripts/monitor.ps1** to display compact current-epoch and overall ETA.

Use the Python environment at C:/Users/Rio/anaconda3/python.exe. The required
packages are torch, numpy, opencv-python, pandas, and pytest. MATLAB is needed
only for the existing external ACM validation bridge.

## What changed

1. Signed distance and its normal use the same orientation, including dark
   objects. The distance orientation is learned; no foreground-polarity input
   or truth is required at inference.
2. Width rendering is continuous at zero correction. Reference endpoints are
   sampled from the consistent coordinate system rather than unrelated
   sliding neighborhoods. Corrections are integrated from a 2x grid.
3. The reflection projection and repeated forced high-pass operations are
   removed. Detail can be learned directly under geometric and pixel evidence.
   This is not a mathematical guarantee against hallucination: held-out
   image, geometry, and displacement validation remain necessary.
4. The geometry estimator continues to learn in action and detail stages.
   No logged training loss is silently omitted from the total objective.
5. Actual two-dimensional localization and paired restored-reference errors
   replace the whole-object signed radial average and equal-action penalties.
   Flat/unidentifiable regions do not supply position evidence.
6. Boundary losses are normalized per scene before batch averaging. Each
   scene is consumed once per epoch; no extra clear view is appended.
7. Optical observations are blurred at 8x resolution, then sensor-integrated.
   The existing 5,000/512 antialiased shape references are reused as immutable
   hardlinks. Only new observations are materialized. Sensor noise and shared
   source/reference exposure are varied in the dataset.
8. Every real preview checks the verified pre-R109 Raw checksum.
9. R73, R74, SEM, and reused development scenes are labeled development
   evaluations. A separate 144-scene synthetic confirmation set is generated
   and sealed without evaluating models on it.
10. Fine-detail supervision distinguishes optically erased texture from
    denoising. Reliability is derived from known clean synthetic observations
    and sensor noise, and multiplies the actual error rather than being
    normalized away in the averaging denominator. Flat targets retain
    denoising supervision. The reliability map is never an inference input.

## Scope

The optical kernels are explicit synthetic priors, not claimed to be a
uniquely identified physical PSF of the microscope. The reference crops have
verified pre-R109 provenance; camera-original lineage should be retained when
new captures are introduced. No real SEM structure or real image pixels enter
training. External GMF is not a thesis model-selection criterion.

The least-squares localization loss is locally accurate for small shifts. It
is a training aid, not a replacement for locked ACM/LSC validation on real
images. Boundary prediction quality and corners/thin gaps remain empirical
validation targets.

## Validation

- python -m pytest tests -q
- python validation/preflight.py
- python training/train.py --mode probe --epochs 12 --limit 512 --batch 8
- python validation/locked_acm.py --checkpoint PATH --output NEW_DIRECTORY --method-name R118 --suite R73 R74
- python validation/sem.py --checkpoint PATH --output NEW_DIRECTORY --name R118

READY.json records repair and execution readiness. It does not promote a short
probe to a thesis or enterprise model.

The final distance convention remains positive inside the synthetic foreground,
with normals taken from that same field. A brightness-oriented alternative was
rejected after a longer matched probe despite a favorable tiny early test.

The model's final trained capability must be assessed after full training.
Short repair probes are not substituted for a completed, independently
validated thesis or enterprise release.
