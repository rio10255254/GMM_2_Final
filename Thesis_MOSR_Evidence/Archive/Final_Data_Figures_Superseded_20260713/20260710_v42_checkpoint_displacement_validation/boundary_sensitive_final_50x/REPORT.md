# V42 checkpoint comparison on 50x real displacement sequences

Method: fixed manual ROI, Sobel edge projection, one-dimensional profile matching, and subpixel parabolic refinement. All six cases use the same ROI, image order, signed direction and selections.

## Winner summary

| group | selection | best model | best step SD (um) | improvement vs Raw |
|---|---|---|---:|---:|
| x_1um | all_steps | V42 epoch 94 | 0.010552 | +18.16% |
| x_1um | common_best30 | V42 epoch 94 | 0.005065 | +34.09% |
| x_1um | raw_anchor_best30 | Old V41 | 0.005726 | +2.17% |
| x_0p5um | all_steps | V42 epoch 94 | 0.038445 | +0.22% |
| x_0p5um | common_best30 | V42 epoch 94 | 0.003130 | +24.00% |
| x_0p5um | raw_anchor_best30 | V42 epoch 94 | 0.003859 | -2.20% |

## Full comparison

| group | selection | case | n | step SD (um) | median abs error (um) | improvement vs Raw |
|---|---|---|---:|---:|---:|---:|
| x_0p5um | all_steps | Raw | 50 | 0.038528 | 0.005852 | +0.00% |
| x_0p5um | all_steps | Old V41 | 50 | 0.038473 | 0.004595 | +0.14% |
| x_0p5um | all_steps | V41-Standalone | 50 | 0.038473 | 0.004610 | +0.14% |
| x_0p5um | all_steps | V42 epoch 10 | 50 | 0.038461 | 0.004482 | +0.17% |
| x_0p5um | all_steps | V42 epoch 23 | 50 | 0.038462 | 0.004494 | +0.17% |
| x_0p5um | all_steps | V42 epoch 94 | 50 | 0.038445 | 0.004626 | +0.22% |
| x_0p5um | common_best30 | Raw | 30 | 0.004119 | 0.003365 | +0.00% |
| x_0p5um | common_best30 | Old V41 | 30 | 0.003319 | 0.002397 | +19.42% |
| x_0p5um | common_best30 | V41-Standalone | 30 | 0.003267 | 0.002437 | +20.68% |
| x_0p5um | common_best30 | V42 epoch 10 | 30 | 0.003170 | 0.002401 | +23.02% |
| x_0p5um | common_best30 | V42 epoch 23 | 30 | 0.003148 | 0.002420 | +23.58% |
| x_0p5um | common_best30 | V42 epoch 94 | 30 | 0.003130 | 0.002415 | +24.00% |
| x_0p5um | raw_anchor_best30 | Raw | 30 | 0.003776 | 0.003365 | +0.00% |
| x_0p5um | raw_anchor_best30 | Old V41 | 30 | 0.004072 | 0.002397 | -7.83% |
| x_0p5um | raw_anchor_best30 | V41-Standalone | 30 | 0.003963 | 0.002437 | -4.93% |
| x_0p5um | raw_anchor_best30 | V42 epoch 10 | 30 | 0.003887 | 0.002401 | -2.92% |
| x_0p5um | raw_anchor_best30 | V42 epoch 23 | 30 | 0.003893 | 0.002420 | -3.08% |
| x_0p5um | raw_anchor_best30 | V42 epoch 94 | 30 | 0.003859 | 0.002415 | -2.20% |
| x_1um | all_steps | Raw | 49 | 0.012895 | 0.009341 | +0.00% |
| x_1um | all_steps | Old V41 | 49 | 0.010734 | 0.008081 | +16.75% |
| x_1um | all_steps | V41-Standalone | 49 | 0.010809 | 0.008419 | +16.17% |
| x_1um | all_steps | V42 epoch 10 | 49 | 0.010764 | 0.007963 | +16.52% |
| x_1um | all_steps | V42 epoch 23 | 49 | 0.010715 | 0.007927 | +16.90% |
| x_1um | all_steps | V42 epoch 94 | 49 | 0.010552 | 0.008107 | +18.16% |
| x_1um | common_best30 | Raw | 30 | 0.007685 | 0.006426 | +0.00% |
| x_1um | common_best30 | Old V41 | 30 | 0.005299 | 0.005430 | +31.04% |
| x_1um | common_best30 | V41-Standalone | 30 | 0.005279 | 0.005313 | +31.31% |
| x_1um | common_best30 | V42 epoch 10 | 30 | 0.005231 | 0.005193 | +31.93% |
| x_1um | common_best30 | V42 epoch 23 | 30 | 0.005192 | 0.005039 | +32.43% |
| x_1um | common_best30 | V42 epoch 94 | 30 | 0.005065 | 0.004817 | +34.09% |
| x_1um | raw_anchor_best30 | Raw | 30 | 0.005853 | 0.006426 | +0.00% |
| x_1um | raw_anchor_best30 | Old V41 | 30 | 0.005726 | 0.005966 | +2.17% |
| x_1um | raw_anchor_best30 | V41-Standalone | 30 | 0.005811 | 0.005727 | +0.71% |
| x_1um | raw_anchor_best30 | V42 epoch 10 | 30 | 0.005831 | 0.005514 | +0.38% |
| x_1um | raw_anchor_best30 | V42 epoch 23 | 30 | 0.005783 | 0.005415 | +1.20% |
| x_1um | raw_anchor_best30 | V42 epoch 94 | 30 | 0.005778 | 0.005462 | +1.28% |
