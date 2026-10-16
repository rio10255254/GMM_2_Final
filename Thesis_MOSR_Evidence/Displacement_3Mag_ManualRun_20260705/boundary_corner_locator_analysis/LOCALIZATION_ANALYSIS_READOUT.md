# Boundary and Corner Localization Analysis

This test reuses the current manual ROI from the previous edge-phase run. It intentionally uses boundary/corner-dependent localization instead of phase correlation or external GMF.

## Methods

- Boundary centroid: finds the weighted center of strong edge pixels inside the selected ROI.

- Corner tracking: detects corner-like points inside the selected ROI and tracks their median motion from one frame to the next.

## Data coverage

- Cases processed: 12

- Step rows produced: 1180

- ROI source: source_manifest/run_manifest.json from the manual ROI run.

## All steps - boundary centroid

| Dataset | Raw med. error | R61 med. error | Raw std | R61 std | Raw <=0.05um | R61 <=0.05um |
|---|---:|---:|---:|---:|---:|---:|
| 50x_1um | 0.8541 | 0.8503 | 0.0915 | 0.1017 | 0.0% | 0.0% |
| 50x_0p5um | 0.4289 | 0.3949 | 0.0637 | 0.0646 | 0.0% | 0.0% |
| 20x_1um | 0.8190 | 0.7348 | 0.2391 | 0.1761 | 0.0% | 0.0% |
| 20x_0p5um | 0.3580 | 0.3535 | 0.1184 | 0.1380 | 4.1% | 4.1% |
| 5x_1um | 0.5887 | 0.9093 | 0.3169 | 1.4727 | 2.0% | 2.0% |
| 5x_0p5um | 0.2297 | 0.6437 | 0.2061 | 1.0785 | 8.2% | 6.1% |


## All steps - corner tracking

| Dataset | Raw med. error | R61 med. error | Raw std | R61 std | Raw <=0.05um | R61 <=0.05um |
|---|---:|---:|---:|---:|---:|---:|
| 50x_1um | 0.2729 | 0.2731 | 0.0067 | 0.0064 | 0.0% | 0.0% |
| 50x_0p5um | 0.1366 | 0.1361 | 0.0380 | 0.0378 | 0.0% | 0.0% |
| 20x_1um | 0.2726 | 0.2735 | 0.0185 | 0.0183 | 0.0% | 0.0% |
| 20x_0p5um | 0.1369 | 0.1384 | 0.0556 | 0.0554 | 2.0% | 2.0% |
| 5x_1um | 0.3250 | 0.3519 | 0.1170 | 0.1277 | 2.0% | 2.0% |
| 5x_0p5um | 0.1432 | 0.1847 | 0.0085 | 0.0092 | 0.0% | 0.0% |


## Best 30 matched steps - boundary centroid

| Dataset | Raw med. error | R61 med. error | Raw std | R61 std | Raw <=0.05um | R61 <=0.05um |
|---|---:|---:|---:|---:|---:|---:|
| 50x_1um | 0.8343 | 0.8171 | 0.0665 | 0.0731 | 0.0% | 0.0% |
| 50x_0p5um | 0.3517 | 0.3460 | 0.0543 | 0.0537 | 0.0% | 0.0% |
| 20x_1um | 0.6877 | 0.6631 | 0.2280 | 0.1663 | 0.0% | 0.0% |
| 20x_0p5um | 0.3397 | 0.2721 | 0.1175 | 0.1211 | 6.7% | 6.7% |
| 5x_1um | 0.6633 | 0.5125 | 0.2737 | 0.6054 | 3.3% | 3.3% |
| 5x_0p5um | 0.2353 | 0.3880 | 0.1762 | 0.4503 | 6.7% | 10.0% |


## Best 30 matched steps - corner tracking

| Dataset | Raw med. error | R61 med. error | Raw std | R61 std | Raw <=0.05um | R61 <=0.05um |
|---|---:|---:|---:|---:|---:|---:|
| 50x_1um | 0.2707 | 0.2707 | 0.0054 | 0.0052 | 0.0% | 0.0% |
| 50x_0p5um | 0.1340 | 0.1338 | 0.0101 | 0.0100 | 0.0% | 0.0% |
| 20x_1um | 0.2687 | 0.2699 | 0.0119 | 0.0123 | 0.0% | 0.0% |
| 20x_0p5um | 0.1315 | 0.1306 | 0.0200 | 0.0202 | 3.3% | 3.3% |
| 5x_1um | 0.2958 | 0.3199 | 0.0945 | 0.1028 | 3.3% | 3.3% |
| 5x_0p5um | 0.1417 | 0.1800 | 0.0076 | 0.0067 | 0.0% | 0.0% |


## Preliminary interpretation

- Boundary centroid is not reliable as a displacement proof here because the selected ROI often contains multiple mixed structures, so the weighted center changes with scene composition, not only translation.

- Corner tracking is closer to the desired boundary-localization test. It is weaker than phase/GMF and exposes cases where reconstruction can help or hurt.

- The current ROI was chosen for phase-style matching, not for isolating one clean physical boundary or one clean square. For a thesis-grade boundary proof, the ROI should isolate one repeated local structure or one square corner field.
