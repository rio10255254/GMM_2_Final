# Step Clean Recopy Audit Report

## Why This Audit Was Run

The previous Step result looked suspicious because the raw selected-position motion was about 0.74 px, while R39/v14/v16 reconstructions measured about 8 px.

This audit re-copied the actual images from the original Step folder and reran the whole check to rule out an operational mistake.

## Clean Dataset Built

Source folder:

`Step`

Clean audit folder:

`Step_analysis_20260623/clean_step_audit_from_original_pos10_20260623_2218`

Images copied:

- positions 0, 10, 20, ..., 390;
- both replicate images per selected position;
- 80 full-size BMP images copied from the original Step folder;
- 80 new center 2048 x 2048 crops generated from those copies.

Crop rule:

- original size: 5120 x 5120;
- center crop: 2048 x 2048;
- crop left/top: 1536, 1536.

## File Integrity Checks

The newly generated center-crop images were compared against the previous center-crop input folder.

Result:

- old center-crop count: 80;
- new center-crop count: 80;
- filename differences: 0;
- content hash mismatches: 0.

This means the old center-crop input was the same image set as the clean recopy. There is no evidence that the wrong raw images were used.

## Clean Raw Motion Result

Using the clean raw center-crop images, the original Step probe's intensity-based phase correlation produced this:

| measurement | value px | value um |
|---|---:|---:|
| same-position repeat median magnitude | 0.019576 | 0.002447 |
| selected pos10 step median dx | 0.742537 | 0.092817 |
| selected pos10 step median magnitude | 0.742768 | 0.092846 |
| selected pos10 step std dx | 0.061380 | 0.007672 |

Conversion used:

`2.5 um / 20x = 0.125 um/px`

Important interpretation:

This intensity-based result looked like the selected position 0 -> 10 step was about 0.093 um. However, a follow-up edge-based check showed this was not a reliable raw-motion estimate.

The intensity response for the raw selected-step measurement was very low, while the edge-based measurement had a stronger response and agreed with the reconstructions.

Edge-based raw result:

| measurement | value px |
|---|---:|
| raw selected pos10 step median dx | 8.004661 |
| raw selected pos10 step median magnitude | 8.013791 |
| raw selected pos10 step std dx | 0.474151 |
| raw selected pos10 median response | 0.435139 |

This means the selected pos10 sequence should not be reclassified as 0.1 um based on the intensity-only result. The stronger current interpretation is that the intensity-only raw probe failed on this low-contrast/blurry raw image, while the edge-based raw probe recovers the expected about-8-px motion.

## Clean Reconstruction Rerun

The clean center-crop input was reconstructed again with:

- R39 a970;
- v14 motion texture;
- v16 Step guard.

All three reruns produced 80 BMP outputs.

The fresh reconstruction outputs were compared against the previous reconstruction folders:

| case | old count | new count | hash mismatches |
|---|---:|---:|---:|
| R39 | 80 | 80 | 0 |
| v14 | 80 | 80 | 0 |
| v16 | 80 | 80 | 0 |

This means the previous reconstruction outputs were reproducible from the clean input. There is no evidence that the old reconstruction folders were mixed or stale.

## Clean Raw/R39/v14/v16 Motion Result

Intensity-based probe result:

| case | repeat median mag px | step median dx px | step median dx um | step std dx px |
|---|---:|---:|---:|---:|
| clean raw | 0.019576 | 0.742537 | 0.092817 | 0.061380 |
| R39 clean rerun | 0.134328 | 8.024669 | 1.003084 | 0.097845 |
| v14 clean rerun | 0.133604 | 8.026425 | 1.003303 | 0.097870 |
| v16 clean rerun | 0.133817 | 8.025998 | 1.003250 | 0.097913 |

The reconstruction-to-raw displacement ratio is roughly:

`8.026 / 0.743 = 10.8x`

This ratio is an artifact of comparing reconstruction results against the weak raw intensity-based estimate.

Edge-based probe result:

| case | repeat median mag px | step median dx px | step std dx px | step median mag px | step median response |
|---|---:|---:|---:|---:|---:|
| clean raw | 0.025634 | 8.004661 | 0.474151 | 8.013791 | 0.435139 |
| R39 clean rerun | 0.116526 | 8.039430 | 0.110595 | 8.040155 | 0.920712 |
| v14 clean rerun | 0.113109 | 8.038949 | 0.110916 | 8.039039 | 0.916855 |
| v16 clean rerun | 0.113730 | 8.038221 | 0.111570 | 8.038403 | 0.914067 |

Edge-based summary:

`Step_analysis_20260623/clean_step_audit_from_original_pos10_20260623_2218/CLEAN_STEP_MOTION_EDGE_RAW_R39_V14_V16_SUMMARY.md`

## Audit Conclusion

This does not look like a file-copy, file-order, old-cache, or wrong-folder mistake.

The clean recopy reproduced the same files and reconstructions. The apparent "10x amplification" was caused by the raw intensity-based motion probe underestimating motion, not by the model physically magnifying the displacement.

Current interpretation:

- old and clean outputs match by hash;
- raw intensity phase correlation is unreliable for this selected-step measurement;
- raw edge-based phase correlation gives about 8 px;
- R39, v14, and v16 also give about 8 px;
- the selected pos10 sequence is consistent with the expected 1 um / 8 px motion under edge-based measurement.

The remaining real issue is not scale amplification. The remaining issue is stability:

- raw edge-based step std dx is much noisier than reconstruction;
- reconstructed R39/v14/v16 step std values are close to each other;
- v16 is still slightly worse than R39/v14 on this Step stability metric.

Do not use the old intensity-only raw result to claim reconstruction scale amplification.
