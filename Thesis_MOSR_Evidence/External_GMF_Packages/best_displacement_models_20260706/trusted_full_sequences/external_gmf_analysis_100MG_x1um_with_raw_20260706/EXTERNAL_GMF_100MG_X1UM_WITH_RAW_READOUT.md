# External GMF 100MG x_1um readout with Raw

This report adds Raw to the returned external GMF scores and compares Raw, V28, V31, V35, and V41 under the same consecutive-step calculation.

External-GMF expected step guard used here: 14.600 coordinate px ~= 1 um.

| rank | case | steps | mean step px | std step px | approx std um | improvement vs Raw | CV | min score | outliers |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | v28 | 48 | 14.5431 | 0.1093 | 0.00749 | +1.49% | 0.752% | 99.253 | 1 |
| 2 | raw | 48 | 14.5433 | 0.1110 | 0.00760 | +0.00% | 0.763% | 99.247 | 2 |
| 3 | v41 | 48 | 14.5430 | 0.1117 | 0.00765 | -0.61% | 0.768% | 99.237 | 1 |
| 4 | v35 | 48 | 14.5437 | 0.1180 | 0.00808 | -6.30% | 0.811% | 99.371 | 1 |
| 5 | v31 | 48 | 14.5431 | 0.1200 | 0.00822 | -8.11% | 0.825% | 99.343 | 1 |

## Common-Step Filters

| filter | rank | case | steps | std step px | approx std um | improvement vs Raw | mean step px |
|---|---:|---|---:|---:|---:|---:|---:|
| drop_common_1to2_and_5to6 | 1 | raw | 46 | 0.0803 | 0.00550 | +0.00% | 14.5472 |
| drop_common_1to2_and_5to6 | 2 | v28 | 46 | 0.0842 | 0.00576 | -4.84% | 14.5472 |
| drop_common_1to2_and_5to6 | 3 | v41 | 46 | 0.0849 | 0.00582 | -5.79% | 14.5475 |
| drop_common_1to2_and_5to6 | 4 | v35 | 46 | 0.0908 | 0.00622 | -13.05% | 14.5462 |
| drop_common_1to2_and_5to6 | 5 | v31 | 46 | 0.0920 | 0.00630 | -14.64% | 14.5474 |
| best30_closest_to_own_median | 1 | raw | 30 | 0.0368 | 0.00252 | +0.00% | 14.5542 |
| best30_closest_to_own_median | 2 | v41 | 30 | 0.0432 | 0.00296 | -17.58% | 14.5550 |
| best30_closest_to_own_median | 3 | v28 | 30 | 0.0445 | 0.00304 | -20.92% | 14.5374 |
| best30_closest_to_own_median | 4 | v35 | 30 | 0.0486 | 0.00333 | -32.26% | 14.5688 |
| best30_closest_to_own_median | 5 | v31 | 30 | 0.0506 | 0.00347 | -37.61% | 14.5562 |

## Common Worst Steps

These are shared step deviations across Raw and reconstructions. Shared deviations are less likely to be model-specific.

| step | mean x step px | across-case range px | deviation from common median px |
|---|---:|---:|---:|
| 1->2 | 14.0920 | 0.0400 | 0.4551 |
| 5->6 | 14.8164 | 0.0740 | 0.2693 |
| 15->16 | 14.3690 | 0.0920 | 0.1781 |
| 2->3 | 14.7200 | 0.0600 | 0.1729 |
| 18->19 | 14.3774 | 0.0430 | 0.1697 |
| 17->18 | 14.7074 | 0.0410 | 0.1603 |
| 34->35 | 14.4094 | 0.0950 | 0.1377 |
| 30->31 | 14.6834 | 0.0460 | 0.1363 |
