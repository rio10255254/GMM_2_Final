# Epoch Screen

- evaluated_epochs: [20, 40]
- abort_after_40: False

| line | epoch | edge_w_main | slope_main | CNR_main | bg_std | cb_ratio | thickness_std |
| --- | --- | --- | --- | --- | --- | --- | --- |
| old_psf | 10 | 33.74 | 6.49 | 19.71 | 0.613 | 0.121 | 4.290 |
| old_psf | 20 | 35.69 | 6.34 | 19.73 | 0.505 | 0.133 | 4.621 |
| old_psf | 40 | 35.27 | 6.51 | 15.94 | 0.486 | 0.141 | 4.606 |
| new_psf | 10 | 33.74 | 6.51 | 19.95 | 0.610 | 0.121 | 4.345 |
| new_psf | 20 | 35.67 | 6.34 | 19.66 | 0.501 | 0.131 | 4.629 |
| new_psf | 40 | 35.31 | 6.53 | 15.89 | 0.489 | 0.142 | 4.652 |

主判定只看主邊界 width、max slope、CNR_main、background_std；若 new_psf 在 epoch 20 與 40 都同時更差，就視為不能直接接舊 recipe。