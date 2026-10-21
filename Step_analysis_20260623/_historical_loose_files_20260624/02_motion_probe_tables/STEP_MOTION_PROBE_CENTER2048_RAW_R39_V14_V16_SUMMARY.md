# Step Motion Probe

This is an image-only Step guard. It checks repeat captures and selected position +10 pairs.

| case | selected positions | repeat median mag px | repeat p95 mag px | step median dx px | step std dx px | step median mag px | step median response |
|---|---:|---:|---:|---:|---:|---:|---:|
| raw_step_center2048 | 40 | 0.019576 | 0.038445 | 0.742537 | 0.061380 | 0.742768 | 0.088336 |
| 01_r39_a970_step_1um_center2048 | 40 | 0.134328 | 0.278696 | 8.024669 | 0.097845 | 8.025572 | 0.954869 |
| 02_v14_motion_texture_step_1um_center2048 | 40 | 0.133604 | 0.278116 | 8.026425 | 0.097870 | 8.026748 | 0.954097 |
| 03_v16_stepguard_step_1um_center2048 | 40 | 0.133817 | 0.278882 | 8.025998 | 0.097913 | 8.026330 | 0.954373 |

The selected Step sequence is commanded by position index. The physical pixel scale mismatch remains an open calibration issue.
