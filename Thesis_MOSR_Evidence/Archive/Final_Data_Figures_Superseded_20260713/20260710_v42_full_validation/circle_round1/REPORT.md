# Circle Round1 Geometry Repeatability

The first 50 filename-sorted captures were cropped at fixed coordinates without resizing. Frames where Raw does not contain a complete central circle are excluded by geometry visibility only; Raw and V42 then use the same filenames.
Valid complete-circle frames: 10 / 50.
This dataset has no per-frame traceable diameter truth, so the result supports repeatability and roundness only, not absolute CD accuracy.

| case     |   n_frames |   mean_radius_px |   radius_std_px |   center_x_std_px |   center_y_std_px |   mean_radial_rms_px |   median_radial_rms_px |   mean_roundness_p95_p05_px |
|:---------|-----------:|-----------------:|----------------:|------------------:|------------------:|---------------------:|-----------------------:|----------------------------:|
| raw      |         10 |        396.20585 |         0.07250 |         344.75340 |         348.94075 |              0.32790 |                0.32647 |                     1.06682 |
| v42_e120 |         10 |        396.61301 |         0.07303 |         344.76869 |         348.94591 |              0.36295 |                0.35908 |                     1.18965 |
