# Fast Edge Step Stability Report

Expected step: 0.100 um = 0.8000 px (0.1250 um/px).

## Main Edge Full 2048 Step Result

| Case | Median dx px | Std px | Std um | P95 abs err um | Response | Confidence | Improvement vs Raw |
|---|---:|---:|---:|---:|---:|---|---:|
| Raw | 0.1074 | 0.0217 | 0.00272 | 0.09095 | 0.3559 | low | 1.00 |
| R39 | 0.8552 | 0.0953 | 0.01192 | 0.02575 | 0.9603 | high | 0.23 |
| v14 | 0.8565 | 0.0951 | 0.01188 | 0.02580 | 0.9608 | high | 0.23 |
| v16 | 0.8561 | 0.0952 | 0.01190 | 0.02576 | 0.9608 | high | 0.23 |

## Same Position Repeat Floor

| Case | Median dx px | Std px | Std um | Response | Confidence |
|---|---:|---:|---:|---:|---|
| Raw | 0.0002 | 0.0215 | 0.00269 | 0.3632 | medium |
| R39 | -0.0099 | 0.0820 | 0.01025 | 0.9603 | high |
| v14 | -0.0090 | 0.0816 | 0.01020 | 0.9609 | high |
| v16 | -0.0098 | 0.0818 | 0.01022 | 0.9607 | high |

## Center 1024 Check

| Case | Median dx px | Std px | Std um | P95 abs err um | Response | Confidence |
|---|---:|---:|---:|---:|---:|---|
| Raw | 0.1047 | 0.0984 | 0.01230 | 0.09483 | 0.3381 | low |
| R39 | 0.8498 | 0.1002 | 0.01252 | 0.02605 | 0.9800 | high |
| v14 | 0.8507 | 0.0999 | 0.01249 | 0.02596 | 0.9802 | high |
| v16 | 0.8499 | 0.1001 | 0.01252 | 0.02605 | 0.9802 | high |
