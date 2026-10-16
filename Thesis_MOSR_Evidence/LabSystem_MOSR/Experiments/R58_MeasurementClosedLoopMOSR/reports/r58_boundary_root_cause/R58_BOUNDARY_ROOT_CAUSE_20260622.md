# R58 Boundary Root-Cause Check

Generated: 2026-06-22

## Short conclusion

The current R58 model is not failing mainly because of PSF. The boundary is inaccurate because the training setup does not actually teach the model the true SEM boundary.

The strongest causes are:

1. The `r58_frac050` labels are not SEM-correct labels. They intentionally apply only 50% of the correction.
2. The full training package contains only synthetic ideal circular anchors: 4096 anchor pairs, 0 base pairs.
3. The geometry sidecars are generated from the synthetic label images, not from SEM-derived masks.
4. The model outputs only one grayscale reconstructed image, not a boundary map or radius/CD prediction.
5. The training loss mostly rewards visual image similarity and edge strength. CD is logged/gated externally, but it is not a direct training target.
6. The selected best checkpoint stayed at epoch 2 even though later validation reconstruction metrics improved through epoch 30.

## Evidence

### Training-data manifest

Manifest checked:

`LabSystem_MOSR/Training_Data/r60_full_power/hs100mg_basler/r58_frac050_train/manifest.json`

Key values:

- camera: Basler ace acA2040-120um
- nm_per_px: 69
- correction_fraction: 0.5
- base_pairs: 0
- anchor_pairs: 4096
- total_pairs: 4096
- geometry_count: 4096

Per-feature target bias in the training labels:

| feature | pairs | SEM radius nm | source bias nm | target label bias nm |
| --- | ---: | ---: | ---: | ---: |
| pillar | 2048 | 1321.88 | +11.04 | +5.52 |
| via | 2048 | 1642.00 | -66.13 | -33.07 |

This means a perfect learner of `r58_frac050` would still not match SEM. The via label is still 33.07 nm smaller than SEM, and the pillar label is still 5.52 nm larger than SEM.

### Dataset generator

The R58 dataset generator computes the target radius as:

`target = source + (SEM - source) * correction_fraction`

For `r58_frac050`, this is only a halfway correction. Anchor source images are produced from ideal generated circle geometry with blur/noise styling, not cropped directly from the real 100MG camera image. Boundary/centerline/distance geometry files are also generated from these synthetic labels.

### Model and objective

The model output path is:

- one grayscale output image
- optional sigmoid
- no explicit boundary-map head
- no explicit radius/CD head

The boundary geometry loss compares Sobel edge maps and masked pixel values against the synthetic label. It does not directly measure a fitted circle radius against SEM radius.

Loss composition examples from the R58 full run:

| epoch | rec weighted | grad weighted | boundary weighted | boundary share | grad share |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2 | 0.000861419 | 0.004943746 | 0.002030664 | 25.92% | 63.09% |
| 30 | 0.000675343 | 0.003313635 | 0.001745666 | 28.56% | 54.20% |

Boundary loss is present, but it is tied to the synthetic label boundary. It is not tied to the SEM radius error.

### Checkpoint selection

R58 full training ran for 30 epochs, but the selected best checkpoint stayed at epoch 2.

At epoch 30:

- validation reconstruction improved to Rec=0.000651 and SSIM=0.9916
- update was skipped because the best window was E001-E008
- oversmooth/band guards were still firing

So the selected checkpoint was not chosen by real CD error.

### Real CD result

The R58 full reconstruction was worse than the original camera image on mean absolute radius error:

| image | via radius error nm | pillar radius error nm | mean abs radius error nm |
| --- | ---: | ---: | ---: |
| original | -66.13 | +11.04 | 38.59 |
| R58 full | -75.08 | +32.30 | 53.69 |

This is consistent with the root cause: the model learned an image-to-image synthetic correction and did not learn the true SEM boundary.

## Practical implication

R59 same-sample correction worked only because the remaining bias was stable. It should not be claimed as raw model accuracy.

For the next clean version, the model needs real SEM-boundary supervision or a direct differentiable CD/radius objective, plus real-image crops and blind validation. Otherwise it can keep improving visual sharpness while making CD worse.
