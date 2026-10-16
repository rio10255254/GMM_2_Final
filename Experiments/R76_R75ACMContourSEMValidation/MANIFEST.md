# R76 frozen manifest

## Scientific question

Does the R75 model trained from random initialization on pure synthetic primitive shapes make the complete, non-circular optical pillar outline closer to the matched SEM outline than the raw optical image? How does it compare with the previously tested R61v16 and V42E120 models?

## Identity and pairing lock

- SEM truth is `P-01.tiff` through `P-09.tiff`, four physical pillars per image and 36 pillars total.
- The current SEM files are independently checked against the legacy SEM folder by SHA-256. All 18 P/V files must match byte for byte.
- The 36 identities are recovered from the legacy `SEM2img_v2.m` placement logic and cross-checked against the verified ordering package and the R69 mapping table.
- The optical observations are legacy `image_cropped/13.bmp` through `24.bmp`, twelve brightness observations of the same 6x6 field. The locked R69 copies must remain byte-identical to their source.
- Recent 2026 optical displacement images are not used as pillar-level SEM truth because a matching design does not prove that they are the same physical specimen.

## Checkpoint lock

- Training must finish all 100 requested epochs before R76 begins.
- The checkpoint is the R75 training run's internally selected `best_tradeoff.pth.tar` exported by the R75 launcher.
- SEM images and ACM results are never used to choose an epoch or checkpoint.
- The exported manifest must state that no pretrained checkpoint and no teacher model were loaded during R75 training.
- Because the internally selected checkpoint stopped at epoch 21, the terminal epoch 100 checkpoint is also audited as a predeclared selection-rule sensitivity check. It is reported separately and is not silently promoted using SEM results.

## Contour protocol

- The exact frozen R69 MATLAB Chan-Vese extractor is reused: 200 iterations, smooth factor 1.0, 40-pixel seed radius, 45-pixel support radius.
- Each optical mask is aligned to its SEM mask by translation only. No model receives per-pillar scale or rotation fitting.
- Primary measures are IoU, Dice, mean symmetric boundary distance, HD95, area error, perimeter error, and circularity error. No fitted circle or radius is used.
- Bright, middle, and darkest exposures 13, 18, and 24 are repeated under three fixed contour-smoothing settings.

## Statistical unit and gate

- The independent unit is the physical pillar (n=36). Twelve exposures are repeated observations, not 432 independent samples.
- Each pillar is summarized by its median across exposures.
- Paired two-sided Wilcoxon tests, Holm correction, and a fixed-seed 20,000-repeat bootstrap are used.
- The coarse gate requires at least 60% of pillars to improve and a positive 95% bootstrap lower bound for both IoU and mean boundary distance.
- Universal use additionally requires positive median improvement in every tested exposure. Fine-shape fidelity requires both perimeter and circularity error to improve.
