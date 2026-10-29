# Center-square external GMF quick readout, 0.5um rep0

External GMF score was generated only for Raw rep0 and v16 rep0. This readout uses PosX because the returned GMF positions move in X; PosY is treated as transverse drift.

| case | frames | steps | median dx px | std dx px | median abs err um | p95 abs err um | dy std um | mean score | missing first frame |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| raw_rep0 | 78 | 77 | 4.0300 | 0.1984 | 0.01625 | 0.04533 | 0.02593 | 94.66 | True |
| v16_rep0 | 78 | 77 | 4.0070 | 0.1434 | 0.01125 | 0.03305 | 0.01978 | 99.84 | True |

Expected 0.5um step = 4 px = 0.5um with 0.125um/px calibration.

Primary interpretation: lower absolute error versus 4px and higher Score0 indicate better center-square GMF alignment.