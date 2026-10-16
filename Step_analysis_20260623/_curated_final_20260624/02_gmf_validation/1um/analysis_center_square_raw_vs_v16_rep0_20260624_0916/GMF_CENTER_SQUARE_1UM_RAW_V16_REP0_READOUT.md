# Center-square external GMF quick readout, 1um rep0

External GMF score was generated only for Raw rep0 and v16 rep0. This readout uses PosX because the returned GMF positions move in X; PosY is treated as transverse drift.

| case | frames | steps | median dx px | std dx px | median abs err um | p95 abs err um | dy std um | mean score | missing first frame |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| raw_rep0 | 39 | 38 | 7.9950 | 0.1912 | 0.02119 | 0.04570 | 0.02880 | 94.59 | True |
| v16_rep0 | 39 | 38 | 8.0500 | 0.1289 | 0.01250 | 0.03392 | 0.01814 | 99.84 | True |

Expected 1um step = 8 px = 1um with 0.125um/px calibration.

Primary interpretation: lower absolute error versus 8px and higher Score0 indicate better center-square GMF alignment.