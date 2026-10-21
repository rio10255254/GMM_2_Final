# R127 reusable image-pair measurement

The delivered reader accepts8bit/16bit gray images and color images, preserves integer input depth before conversion, and reports displacement in source-image pixels. It never automatically converts to micrometers or treats a commanded stage move as truth. Existing output files are refused.

```powershell
& C:\Users\Rio\anaconda3\python.exe D:\GMM_2_Final\Experiments\R127_MeasurementPreservationRepair\scripts\measure_pair.py --first C:\Data\frame0.tif --second C:\Data\frame1.tif --output C:\Data\pair_result.json
```

To retain a local diagnostic while using the full images as larger context, add `--roi X Y WIDTH HEIGHT`. The result explicitly distinguishes local validity from the scope of the returned translation. If matching is ambiguous, `displacement_xy_px` is null and the status is `not_uniquely_measurable`. A numeric return is a conditional image-registration estimate, not independently measured stage truth.

The conditional preservation interface is `scripts/preservation.py:reconstruct(model, raw, sensor_noise_sigma_gray=..., evidence_kind=...)`. It preserves raw values only under the stated known procedural identity/noise-free conditions. Ordinary reconstruction is unchanged for other cases. The interface intentionally does not accept a string claiming qualified real instrumentation; that admission path needs actual calibration evidence.

Current independently checked fixed data are under `results/sem_native_v2`; `native_size_comparison` compares the original36objects and two exposures without resizingSEM. This calibration/reference is specific to those source images and must not be applied to a different specimen or pixel grid by copying filenames.

Audit scripts use exclusive result files to preserve history. Repeating a complete experiment requires a separately identified output run; old outputs are not overwritten. No expensive training or cleanup is part of these commands.
