# 20260704 20x/5x displacement reconstruction analysis

Primary readout uses the large sample-pattern ROI, excluding the left background/arrows.
Expected px assumes 3.45 um camera pixels and the folder magnification label.

## Primary ROI, gaps > 30 s excluded

| group | image | steps | expected px | median |dx| px | std |dx| px | median dx px | response | measured / expected |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 20x_1um | Raw | 48 | 5.7971 | 5.8600 | 0.1280 | -5.8600 | 0.9879 | 1.0109 |
| 20x_1um | R61 v16 PSF-off | 48 | 5.7971 | 5.8535 | 0.1411 | -5.8535 | 0.7856 | 1.0097 |
| 20x_0p5um | Raw | 48 | 2.8986 | 2.9093 | 0.2060 | -2.9093 | 0.9878 | 1.0037 |
| 20x_0p5um | R61 v16 PSF-off | 48 | 2.8986 | 2.8792 | 0.2059 | -2.8792 | 0.8290 | 0.9933 |
| 5x_1um | Raw | 43 | 1.4493 | 1.4615 | 0.2359 | -1.4615 | 0.9424 | 1.0085 |
| 5x_1um | R61 v16 PSF-off | 43 | 1.4493 | 1.3433 | 0.1996 | -1.3433 | 0.9303 | 0.9269 |
| 5x_0p5um | Raw | 45 | 0.7246 | 0.6577 | 0.0164 | -0.6577 | 0.9520 | 0.9077 |
| 5x_0p5um | R61 v16 PSF-off | 45 | 0.7246 | 0.7133 | 0.0138 | -0.7133 | 0.9552 | 0.9844 |

## Multi-ROI cross-check, gaps > 30 s excluded

| group | method | Raw median |dx| | R61 v16 median |dx| | expected px | note |
|---|---|---:|---:|---:|---|
| 20x_1um | primary_grid_area_edge | 5.8600 | 5.8535 | 5.7971 | primary |
| 20x_1um | center_blocks_edge | 5.8717 | 5.8698 | 5.7971 |  |
| 20x_1um | line_grating_edge | 5.8614 | 5.8858 | 5.7971 |  |
| 20x_1um | dot_array_edge | 5.8367 | 5.7790 | 5.7971 |  |
| 20x_1um | left_unique_edge | 5.8836 | 5.8162 | 5.7971 | diagnostic; may include background/arrows |
| 20x_1um | full_frame_edge | 5.8411 | 5.8307 | 5.7971 |  |
| 20x_0p5um | primary_grid_area_edge | 2.9093 | 2.8792 | 2.8986 | primary |
| 20x_0p5um | center_blocks_edge | 2.8858 | 2.8606 | 2.8986 |  |
| 20x_0p5um | line_grating_edge | 2.9132 | 2.8862 | 2.8986 |  |
| 20x_0p5um | dot_array_edge | 2.9119 | 2.8262 | 2.8986 |  |
| 20x_0p5um | left_unique_edge | 2.9480 | 2.9192 | 2.8986 | diagnostic; may include background/arrows |
| 20x_0p5um | full_frame_edge | 2.8959 | 2.8282 | 2.8986 |  |
| 5x_1um | primary_grid_area_edge | 1.4615 | 1.3433 | 1.4493 | primary |
| 5x_1um | center_blocks_edge | 1.5101 | 1.2926 | 1.4493 |  |
| 5x_1um | line_grating_edge | 1.4619 | 1.3331 | 1.4493 |  |
| 5x_1um | dot_array_edge | 1.3680 | 1.3074 | 1.4493 |  |
| 5x_1um | left_unique_edge | 1.3540 | 1.2694 | 1.4493 | diagnostic; may include background/arrows |
| 5x_1um | full_frame_edge | 1.4416 | 1.3451 | 1.4493 |  |
| 5x_0p5um | primary_grid_area_edge | 0.6577 | 0.7133 | 0.7246 | primary |
| 5x_0p5um | center_blocks_edge | 0.6303 | 0.7082 | 0.7246 |  |
| 5x_0p5um | line_grating_edge | 0.6579 | 0.6813 | 0.7246 |  |
| 5x_0p5um | dot_array_edge | 0.7194 | 0.7255 | 0.7246 |  |
| 5x_0p5um | left_unique_edge | 0.7078 | 0.7796 | 0.7246 | diagnostic; may include background/arrows |
| 5x_0p5um | full_frame_edge | 0.6759 | 0.7159 | 0.7246 |  |

## Interpretation Notes

- 20x/1um is the cleanest set: both Raw and R61 v16 are near the expected 5.80 px shift.
- 20x/0.5um is usable, but ROI choice changes the median by a few tenths of a pixel.
- 5x/1um and 5x/0.5um are subpixel-to-low-pixel measurements, so ROI choice matters much more.
- R61 v16 reconstruction preserves the displacement direction in all four groups; it does not create a gross motion scaling error.
- This is internal phase-correlation analysis, not an external GMF score.
