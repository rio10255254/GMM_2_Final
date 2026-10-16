# R69 frozen manifest

## Scientific question

Does the frozen R61v16 PSF-off reconstruction make the complete, non-circular optical pillar outline closer to the matched SEM outline than the raw optical image?

## Strictly paired evidence

- SEM truth: `P-01.tiff` through `P-09.tiff` under `H:\From_2TB_D_disk\13_thesis\SEM_data`; four pillars per image, 36 physical pillars total.
- Optical observations: `image_cropped\13.bmp` through `24.bmp` from the legacy SEM data package; these are twelve brightness/exposure observations of the same 6x6 field.
- Pairing authority: `SEM2img_v2.m` explicitly assigns those twelve optical images to P-01 through P-09 and provides the fixed SEM crop and scale. The recovered global 6x6 identities are stored in `results/tables/pillar_mapping.csv`.
- The optical files inside this experiment are byte-preserving copies. The source files are never modified.

The recent 2026 50x displacement images are genuine external observations and remain useful for generalization auditing. They are not used as pillar-level SEM truth here because matching target design alone does not prove the same physical specimen and pillar identity.

## Frozen reconstruction

- Model: R61v16 `best_tradeoff.pth.tar` from the 2026-06-23 v16 training run.
- Inference: CUDA, all BMP files, PSF checkpoint state disabled, weak PSF disabled, deconvolution regularization 30, physical alpha 0.
- Output: twelve reconstructed BMP files under `results/inference_runs`.

## Contour protocol

- MATLAB Chan-Vese active contour, 200 iterations, smooth factor 1.0.
- The initialization begins just outside the SEM rim. A larger outer safety region is audited; accepted masks must not touch it.
- Optical and reconstructed masks are aligned to SEM by translation only. No per-pillar scaling or rotation is allowed.
- SEM edge-acquisition slivers are removed only when a mask reaches the outer 12-pixel cell strip. The deterministic audit triggers for pillar IDs 17 and 28; the central target component is retained. All 36 final SEM masks stay clear of the outer safety region.
- Primary measures: IoU, Dice, mean symmetric boundary distance, boundary HD95, area error, perimeter error, and corrected circularity error. No fitted circle or radius is used.
- Sensitivity audit: three fixed ACM smoothness settings on bright, middle, and darkest exposures 13, 18, and 24.

## Statistical unit and decision rule

The independent unit is the physical pillar (n=36). The twelve exposures are repeated observations, not 432 independent samples. Primary inference uses each pillar's median across exposures, a paired two-sided Wilcoxon test, Holm correction across measures, and a fixed-seed bootstrap confidence interval over the 36 paired pillar improvements.

The coarse-contour gate requires at least 60% of pillars to improve and a positive 95% bootstrap lower bound for both mean boundary distance and IoU. Universal use additionally requires improvement in every tested exposure regime. Fine-shape fidelity requires perimeter and circularity errors to improve.
