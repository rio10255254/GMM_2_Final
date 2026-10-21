# External GMF 100MG x_1um readout

Returned score folders: V28, V31, V35, V41. Raw/V20 were not present in this returned batch, so this report ranks the four returned reconstructions only.

All four score files contain 49 successful position rows, producing 48 consecutive steps per model.

The external GMF coordinate scale is judged with the existing 100MG guard: about 14.6 coordinate px per commanded 1 um step. The um values below are approximate; the relative ranking is the safer comparison.

## All Steps Ranking

| rank | case | steps | mean step px | std step px | approx std um | CV | min score | outliers |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | v28 | 48 | 14.5431 | 0.1093 | 0.00749 | 0.752% | 99.253 | 1 |
| 2 | v41 | 48 | 14.5430 | 0.1117 | 0.00765 | 0.768% | 99.237 | 1 |
| 3 | v35 | 48 | 14.5437 | 0.1180 | 0.00808 | 0.811% | 99.371 | 1 |
| 4 | v31 | 48 | 14.5431 | 0.1200 | 0.00822 | 0.825% | 99.343 | 1 |

## Common-Step Filters

| filter | rank | case | steps | std step px | approx std um | mean step px | delta vs V28 |
|---|---:|---|---:|---:|---:|---:|---:|
| drop_common_1to2_and_5to6 | 1 | v28 | 46 | 0.0842 | 0.00576 | 14.5472 | +0.00% |
| drop_common_1to2_and_5to6 | 2 | v41 | 46 | 0.0849 | 0.00582 | 14.5475 | -0.91% |
| drop_common_1to2_and_5to6 | 3 | v35 | 46 | 0.0908 | 0.00622 | 14.5462 | -7.84% |
| drop_common_1to2_and_5to6 | 4 | v31 | 46 | 0.0920 | 0.00630 | 14.5474 | -9.35% |
| best30_closest_to_own_median | 1 | v41 | 30 | 0.0432 | 0.00296 | 14.5550 | +2.76% |
| best30_closest_to_own_median | 2 | v28 | 30 | 0.0445 | 0.00304 | 14.5374 | +0.00% |
| best30_closest_to_own_median | 3 | v35 | 30 | 0.0486 | 0.00333 | 14.5688 | -9.38% |
| best30_closest_to_own_median | 4 | v31 | 30 | 0.0506 | 0.00347 | 14.5562 | -13.80% |

## Common Worst Steps

These steps are shared deviations across all four models, so they are more likely stage/tool sequence effects than model-specific failures.

| step | mean x step px | across-model range px | deviation from common median px |
|---|---:|---:|---:|
| 1->2 | 14.0950 | 0.0400 | 0.4563 |
| 5->6 | 14.8143 | 0.0740 | 0.2630 |
| 2->3 | 14.7275 | 0.0400 | 0.1763 |
| 15->16 | 14.3783 | 0.0820 | 0.1730 |
| 18->19 | 14.3848 | 0.0170 | 0.1665 |
| 17->18 | 14.7097 | 0.0410 | 0.1585 |
| 31->32 | 14.3940 | 0.0800 | 0.1572 |
| 25->26 | 14.4183 | 0.0870 | 0.1330 |

## Outputs

- Step trace: `external_gmf_step_trace.png`
- Std ranking: `external_gmf_std_ranking.png`
- Position rows: `external_gmf_positions.csv`
- Consecutive steps: `external_gmf_consecutive_steps.csv`
- Filtered stability summary: `external_gmf_filtered_stability_summary.csv`
