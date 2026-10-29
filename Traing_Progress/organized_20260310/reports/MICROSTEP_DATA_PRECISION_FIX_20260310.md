# Microstep Data Precision Fix 2026-03-10

## Problem
External validation showed a clear scale split:
- 1um / 8px: usable
- 0.1um / 0.8px: mean is accurate but step std is too large
- 0.01um / 0.08px: unstable, including negative steps

The most likely root cause on the data side was microstep signal loss before training:
- `stage_17/18` clean renders were saved as `uint8 .bmp`
- PSF convolution + noise output was also quantized back to `uint8`

For `0.08px`, this is not a cosmetic issue. It removes most of the fractional intensity variation created by area downsampling.

## Code Changes
### `Training_Data/Data_Simulaion.py`
- Added per-stage output controls:
  - `output_ext`
  - `save_bit_depth`
- `stage_17_annulus_microstep_clean` now outputs `uint16 .tif`
- `stage_18_annulus_microstep_defect` now outputs `uint16 .tif`
- High-bit-depth stages now resize in `float32` before quantization, preserving area-downsample fractional values.

### `Training_Data/PSF_Convolution.py`
- Switched to multi-extension scan instead of fixed `*.bmp`
- Added dtype-preserving grayscale load
- Convolution and noise now operate in normalized `[0,1]` space
- Output is quantized back to the original bit depth of the input image
- Result: `uint16 tif -> uint16 tif`, instead of silently collapsing back to `uint8`

### `Tools/RebuildMicrostepStages.py`
- Added a dedicated rebuild entrypoint for stages `17/18`
- It regenerates clean data and then regenerates convolved data

## Evidence
Exact-seed comparison on archived `stage_17/1601.bmp` vs new patched generator:
- old dtype: `uint8`
- new dtype: `uint16`
- old unique levels: `142`
- new unique levels: `2404`
- if the new image is down-quantized back to 8-bit, it matches the archived old image exactly:
  - `match_after_downquant = 1.0`
  - `mean_abs_diff_after_downquant = 0.0`

This is the key proof:
- the old data was not wrong in content
- it was losing microstep information by quantization
- the patched path preserves the same image semantics while retaining far more subpixel intensity resolution

## Current Status
- old `uint8` stage_17/18 data were moved out of training roots to:
  - `Training_Data/archived_microstep_uint8_20260310`
- full rebuild is running now
- stdout log:
  - `Traing_Progress/organized_20260310/pending/logs/microstep_rebuild_20260310_134350.out.log`
- stderr log:
  - `Traing_Progress/organized_20260310/pending/logs/microstep_rebuild_20260310_134350.err.log`

## Next Step
After the rebuild completes, the correct next move is not to blindly retune everything at once.
The clean next experiment is:
1. rerun a microstep-focused sweep using the new `uint16` stage 17/18 data
2. compare external GMF on `0.1um` and `0.01um`
3. only then decide whether sequence-aware supervision or stage-specific noise tightening is necessary
