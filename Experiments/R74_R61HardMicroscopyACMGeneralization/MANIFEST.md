# R74 Manifest

- Population: 100 newly generated 512 x 512 grayscale microscopy images.
- Challenge groups: five groups x 20 images.
- Shape balance: each challenge contains four images from each of five exact closed-shape families.
- Truth: exact binary generator geometry, plus a clean rendered label for reconstruction reference.
- Calibration boundary: Raw images and exact masks only; no R61 output may exist when difficulty is frozen.
- Primary comparison: paired Raw versus frozen R61v16 ACM contours.
- Alignment: translation only primary, fixed pixel coordinates secondary; no scale or rotation fitting.
- Robustness: three ACM smoothness settings on three predeclared files per challenge group.
