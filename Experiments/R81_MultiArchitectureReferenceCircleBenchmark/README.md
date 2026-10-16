# R81 Multi-architecture reference-circle benchmark

## Purpose

This experiment expands the thesis comparison from two external learned baselines
to twelve external architectures plus MOSR.  The external roster spans classic
CNNs, attention networks, restoration transformers, the 2025 PFT-SR model, and
the CVPR 2026 UCAN architecture.

## Locked comparison roster

1. SRCNN-x1
2. VDSR-x1
3. DnCNN
4. Base U-Net
5. Compact EDSR-x1
6. Compact RDN-x1
7. Compact RCAN-x1
8. Compact SwinIR-x1
9. Compact NAFNet
10. Compact Restormer
11. Compact PFT-SR-x1 adaptation (CVPR 2025)
12. UCAN-x1 adaptation (CVPR 2026)
13. MOSR V42 (thesis model)

Raw is an acquisition reference and is not counted as a model.  Wiener is kept
only as a separately labelled calibration-region reference and is not part of
the thirteen-model learned comparison.

## Fairness rules

- All twelve external learned baselines are retrained from scratch with the same
  paired MOSR training package, grouped split, and 128-pixel random crop size.
- All newly trained baselines use the same fixed optical input adapter, objective,
  optimizer family, random seed, maximum epoch count, validation schedule, and
  best-validation checkpoint rule used by the existing modern benchmark.
- The PFT-SR progressive-focused core uses the official CUDA operator in float32.
  Its six-layer x1 grayscale adaptation is declared in every table and is not
  presented as an official pretrained PFT-SR score.
- UCAN uses the official 2026 convolution-attention core with a one-channel,
  same-resolution output head and is likewise reported as an adaptation.
- Every model is evaluated on the same locked microscopy frames.
- The native center-nine static images are the PSF and scale calibration region,
  not an independent sample.
- "External" refers to architecture provenance, not an external dataset.  All
  selected displacement frames have corresponding crops in the V42 training
  package, so this is an in-system controlled comparison and not a blind
  generalization benchmark.
- Measurement is performed only by ACM coarse contour, correct-polarity maximum
  gradient inflection points, and LSC/MZC/MIC/MCC reference circles.
- No grayscale threshold, legacy centroid, or post-hoc model-specific frame
  selection is permitted.

## Status

The source roster, Windows PFT-SR operator, and official UCAN source have been verified.  Training,
inference, reference-circle evaluation, and thesis integration are recorded in
the `results` and `reports` folders as they complete.
