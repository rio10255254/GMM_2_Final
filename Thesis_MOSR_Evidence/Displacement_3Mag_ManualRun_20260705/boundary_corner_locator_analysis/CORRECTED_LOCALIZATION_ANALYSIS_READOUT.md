# Corrected Boundary and Corner Localization Analysis

This version fixes the physical-unit conversion by using the pixel sizes in source_cases.csv. The detected pixel shifts from the boundary methods were kept; only the micrometer conversion and summaries were recalculated.

## Current ROI, all steps

### Boundary centroid

| Dataset | Raw med. error | R61 med. error | Raw std | R61 std | Raw <=0.05um | R61 <=0.05um |
|---|---:|---:|---:|---:|---:|---:|
| 50x_1um | 0.7986 | 0.7934 | 0.1263 | 0.1403 | 0.0% | 0.0% |
| 50x_0p5um | 0.4019 | 0.3549 | 0.0879 | 0.0891 | 0.0% | 0.0% |
| 20x_1um | 0.7502 | 0.6340 | 0.3300 | 0.2430 | 6.1% | 0.0% |
| 20x_0p5um | 0.3041 | 0.2978 | 0.1633 | 0.1905 | 4.1% | 4.1% |
| 5x_1um | 0.4607 | 1.2529 | 0.4374 | 2.0323 | 4.1% | 2.0% |
| 5x_0p5um | 0.2314 | 1.0783 | 0.2845 | 1.4884 | 12.2% | 2.0% |

### Corner tracking

| Dataset | Raw med. error | R61 med. error | Raw std | R61 std | Raw <=0.05um | R61 <=0.05um |
|---|---:|---:|---:|---:|---:|---:|
| 50x_1um | 0.0050 | 0.0047 | 0.0092 | 0.0089 | 100.0% | 100.0% |
| 50x_0p5um | 0.0042 | 0.0041 | 0.0524 | 0.0522 | 96.0% | 96.0% |
| 20x_1um | 0.0079 | 0.0075 | 0.0255 | 0.0253 | 91.8% | 91.8% |
| 20x_0p5um | 0.0114 | 0.0103 | 0.0768 | 0.0765 | 89.8% | 89.8% |
| 5x_1um | 0.1122 | 0.1556 | 0.1615 | 0.1762 | 30.6% | 20.4% |
| 5x_0p5um | 0.0095 | 0.0649 | 0.0117 | 0.0127 | 100.0% | 12.2% |

### Boundary projection

| Dataset | Raw med. error | R61 med. error | Raw std | R61 std | Raw <=0.05um | R61 <=0.05um |
|---|---:|---:|---:|---:|---:|---:|
| 50x_1um | 0.0104 | 0.0083 | 0.0136 | 0.0116 | 100.0% | 100.0% |
| 50x_0p5um | 0.0065 | 0.0057 | 0.0525 | 0.0524 | 96.0% | 96.0% |
| 20x_1um | 0.0081 | 0.0079 | 0.0254 | 0.0258 | 91.8% | 91.8% |
| 20x_0p5um | 0.0099 | 0.0093 | 0.0763 | 0.0768 | 89.8% | 87.8% |
| 5x_1um | 0.1265 | 0.2684 | 0.1638 | 0.3448 | 22.4% | 14.3% |
| 5x_0p5um | 0.0236 | 0.1007 | 0.0311 | 0.2137 | 89.8% | 28.6% |


## Current ROI, best 30 matched steps

### Boundary centroid

| Dataset | Raw med. error | R61 med. error | Raw std | R61 std | Raw <=0.05um | R61 <=0.05um |
|---|---:|---:|---:|---:|---:|---:|
| 50x_1um | 0.7714 | 0.7475 | 0.0918 | 0.1009 | 0.0% | 0.0% |
| 50x_0p5um | 0.2954 | 0.2874 | 0.0749 | 0.0741 | 0.0% | 0.0% |
| 20x_1um | 0.5690 | 0.5351 | 0.3146 | 0.2294 | 6.7% | 0.0% |
| 20x_0p5um | 0.2787 | 0.1855 | 0.1621 | 0.1671 | 3.3% | 6.7% |
| 5x_1um | 0.5354 | 0.6061 | 0.3777 | 0.8355 | 3.3% | 3.3% |
| 5x_0p5um | 0.2161 | 0.4189 | 0.2432 | 0.6215 | 20.0% | 3.3% |

### Corner tracking

| Dataset | Raw med. error | R61 med. error | Raw std | R61 std | Raw <=0.05um | R61 <=0.05um |
|---|---:|---:|---:|---:|---:|---:|
| 50x_1um | 0.0024 | 0.0024 | 0.0026 | 0.0026 | 100.0% | 100.0% |
| 50x_0p5um | 0.0022 | 0.0022 | 0.0028 | 0.0028 | 100.0% | 100.0% |
| 20x_1um | 0.0048 | 0.0044 | 0.0053 | 0.0051 | 100.0% | 100.0% |
| 20x_0p5um | 0.0045 | 0.0062 | 0.0072 | 0.0082 | 100.0% | 100.0% |
| 5x_1um | 0.0492 | 0.0876 | 0.0588 | 0.0626 | 50.0% | 33.3% |
| 5x_0p5um | 0.0070 | 0.0584 | 0.0106 | 0.0092 | 100.0% | 20.0% |

### Boundary projection

| Dataset | Raw med. error | R61 med. error | Raw std | R61 std | Raw <=0.05um | R61 <=0.05um |
|---|---:|---:|---:|---:|---:|---:|
| 50x_1um | 0.0068 | 0.0057 | 0.0070 | 0.0064 | 100.0% | 100.0% |
| 50x_0p5um | 0.0041 | 0.0036 | 0.0047 | 0.0043 | 100.0% | 100.0% |
| 20x_1um | 0.0046 | 0.0047 | 0.0053 | 0.0054 | 100.0% | 100.0% |
| 20x_0p5um | 0.0046 | 0.0054 | 0.0070 | 0.0070 | 100.0% | 100.0% |
| 5x_1um | 0.0800 | 0.1774 | 0.1214 | 0.1971 | 23.3% | 23.3% |
| 5x_0p5um | 0.0249 | 0.0542 | 0.0302 | 0.0789 | 93.3% | 46.7% |


## Practical reading

- Boundary projection is the most usable of the three methods for the current ROI.

- At 50x and 20x, boundary projection gives good displacement values, but Raw and R61 remain close.

- At 5x, the commanded motion is close to or below one pixel, so boundary/corner methods become much less reliable.

- The result still does not show a broad displacement-stability advantage from R61; it mainly shows that edge-based displacement can work when the ROI contains enough boundary texture.
