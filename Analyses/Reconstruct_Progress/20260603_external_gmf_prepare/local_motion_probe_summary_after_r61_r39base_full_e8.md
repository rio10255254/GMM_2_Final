# 20260603 Local Motion Probe

This is a local image-only probe. It does not replace the external GMF tool.

| case | frames | median dy px | std dy px | tail median dy px | tail std dy px | response |
|---|---:|---:|---:|---:|---:|---:|
| 00_raw_input | 11 | 5.799600 | 0.287553 | 5.804628 | 0.268818 | 1.148624 |
| 01_r39r40_default | 11 | 5.786297 | 0.283026 | 5.793985 | 0.270858 | 0.967717 |
| 02_reg300_current_best | 11 | 5.782831 | 0.281648 | 5.789663 | 0.269661 | 0.967114 |
| 03_combo_reference | 11 | 5.761817 | 0.279099 | 5.761818 | 0.278135 | 0.980862 |
| 04_psf_bypass_extreme | 11 | 5.778608 | 0.285655 | 5.780401 | 0.274895 | 0.968076 |
| 05_r61_r39_a970_candidate | 11 | 5.814580 | 0.292805 | 5.819024 | 0.278475 | 0.944506 |
| 15_r61_motion_guard_dualgate_full_e8_best | 11 | 5.796762 | 0.286597 | 5.800311 | 0.274026 | 0.952855 |
| 16_r61_motion_guard_r39base_full_e8_best | 11 | 5.814604 | 0.291522 | 5.816221 | 0.277275 | 0.943507 |

Tail values remove only the first interval, matching the earlier warm-up-step caveat.
