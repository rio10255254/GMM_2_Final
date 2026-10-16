# Boundary and Corner Localization Analysis

This rerun reuses the current manual ROI and compares three boundary-dependent methods: boundary centroid, corner tracking, and boundary projection matching.

## Best current method: boundary projection matching

This method collapses the ROI edge signal into an X-direction boundary profile and matches adjacent frames. It is still boundary-based, but avoids the worst failure mode of simple centroid and repeated-corner tracking.

### All steps

| Dataset | Raw med. error | R61 med. error | Raw std | R61 std | Raw <=0.05um | R61 <=0.05um |
|---|---:|---:|---:|---:|---:|---:|
| 50x_1um | 0.2727 | 0.2725 | 0.0098 | 0.0084 | 0.0% | 0.0% |
| 50x_0p5um | 0.1374 | 0.1370 | 0.0381 | 0.0380 | 0.0% | 0.0% |
| 20x_1um | 0.2721 | 0.2723 | 0.0184 | 0.0187 | 0.0% | 0.0% |
| 20x_0p5um | 0.1372 | 0.1367 | 0.0553 | 0.0557 | 2.0% | 2.0% |
| 5x_1um | 0.3503 | 0.3531 | 0.1187 | 0.2498 | 2.0% | 6.1% |
| 5x_0p5um | 0.1352 | 0.1584 | 0.0225 | 0.1549 | 0.0% | 12.2% |


### Best 30 matched steps

| Dataset | Raw med. error | R61 med. error | Raw std | R61 std | Raw <=0.05um | R61 <=0.05um |
|---|---:|---:|---:|---:|---:|---:|
| 50x_1um | 0.2681 | 0.2692 | 0.0056 | 0.0053 | 0.0% | 0.0% |
| 50x_0p5um | 0.1332 | 0.1336 | 0.0099 | 0.0104 | 0.0% | 0.0% |
| 20x_1um | 0.2685 | 0.2678 | 0.0116 | 0.0117 | 0.0% | 0.0% |
| 20x_0p5um | 0.1315 | 0.1320 | 0.0198 | 0.0200 | 3.3% | 3.3% |
| 5x_1um | 0.3181 | 0.2942 | 0.1124 | 0.2179 | 3.3% | 10.0% |
| 5x_0p5um | 0.1296 | 0.1134 | 0.0216 | 0.0891 | 0.0% | 20.0% |


## Why the first two methods are weaker

- Boundary centroid is dragged by mixed structures inside the ROI, so it does not represent one physical boundary.

- Corner tracking often locks onto repeated local patterns and underestimates the true displacement.

- Boundary projection is the cleanest of the three with the current ROI, but it still does not show a broad R61 advantage.
