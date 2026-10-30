# 20260613 Checkboard Strict-Rect Data Pairs

This folder is the usable CAD-reference output for the 20260613 real checkboard images.

Use `data_pairs_valid.csv` or `data_pairs_valid.tsv` for training/evaluation pairs.
These files contain only rows with at least one trusted strict-rectangle GT region.

Pair roles:

- `source_image`: original real Lab-system checkboard frame.
- `gt_image`: strict rectangular white-cell reference generated from that frame.
- `reliable_mask`: mask for pixels that may be used safely with the GT.
- `overlay_check`: visual inspection image only; do not use as GT.

Counts:

- All source frames: 39
- Valid pairs: 36
- Excluded rows: 3

Excluded rows remain in `data_pairs_all.csv` and `data_pairs_all.json` with
`valid_for_training = no` and `exclusion_reason = no_strict_rect_gt`.

Do not use the older probe/final/debug outputs from the previous CAD-reference attempts.
They were removed because they contained non-rectangular or merged GT regions.
