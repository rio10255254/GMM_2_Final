# Phase algorithm final summary

Primary result uses edge-enhanced phase correlation on the main sample-pattern ROI. Physical scale uses Basler 3.45 um camera pixel, 20x = 0.1725 um/px and 5x = 0.69 um/px.

## Edge-phase primary result

| group | image | steps | target um | median um | std um | abs error um | y drift um |
|---|---|---:|---:|---:|---:|---:|---:|
| 20x_1um | R61 v16 PSF-off | 48 | 1.000 | 1.009729 | 0.024332 | 0.009729 | 0.020590 |
| 20x_1um | Raw | 48 | 1.000 | 1.010857 | 0.022082 | 0.010857 | 0.012989 |
| 20x_0p5um | R61 v16 PSF-off | 48 | 0.500 | 0.496660 | 0.035516 | 0.003340 | 0.021034 |
| 20x_0p5um | Raw | 48 | 0.500 | 0.501846 | 0.035530 | 0.001846 | 0.012959 |
| 5x_1um | R61 v16 PSF-off | 43 | 1.000 | 0.926871 | 0.137752 | 0.073129 | 0.008060 |
| 5x_1um | Raw | 43 | 1.000 | 1.008460 | 0.162784 | 0.008460 | 0.013228 |
| 5x_0p5um | R61 v16 PSF-off | 45 | 0.500 | 0.492182 | 0.009543 | 0.007818 | 0.007848 |
| 5x_0p5um | Raw | 45 | 0.500 | 0.453832 | 0.011292 | 0.046168 | 0.008291 |

## Raw vs R61 v16

| group | Raw median | R61 median | Raw std | R61 std | std change | Raw abs error | R61 abs error |
|---|---:|---:|---:|---:|---:|---:|---:|
| 20x_1um | 1.010857 | 1.009729 | 0.022082 | 0.024332 | +10.2% | 0.010857 | 0.009729 |
| 20x_0p5um | 0.501846 | 0.496660 | 0.035530 | 0.035516 | -0.0% | 0.001846 | 0.003340 |
| 5x_1um | 1.008460 | 0.926871 | 0.162784 | 0.137752 | -15.4% | 0.008460 | 0.073129 |
| 5x_0p5um | 0.453832 | 0.492182 | 0.011292 | 0.009543 | -15.5% | 0.046168 | 0.007818 |

## Direct grayscale DFT cross-check

Direct grayscale DFT was run and kept as a cross-check. It is not used as the primary result because it failed on several raw sequences with repeated/low-contrast structures.

| group | Raw median um | R61 median um | Raw abs error um | R61 abs error um |
|---|---:|---:|---:|---:|
| 20x_1um | 1.061737 | 1.010850 | 0.062600 | 0.011713 |
| 20x_0p5um | 0.017250 | 0.507150 | 0.482750 | 0.010600 |
| 5x_1um | 0.179400 | 0.848700 | 0.820600 | 0.185800 |
| 5x_0p5um | 0.124200 | 0.572700 | 0.375800 | 0.072700 |