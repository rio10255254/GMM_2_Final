# Live validation only

`pillar_center9_50x_raw.bmp` is the fixed 232×232 Raw crop containing only the thesis center-nine pillars P22, P23, P24, P28, P29, P30, P34, P35, and P36. It is reconstructed every five epochs for visual observation only.

This image is never placed in the training, validation, or internal-test datasets. Its output does not affect the loss, checkpoint selection, learning-rate schedule, collapse guards, or any other training decision. Exact source and crop coordinates are recorded in `metadata.json`.
