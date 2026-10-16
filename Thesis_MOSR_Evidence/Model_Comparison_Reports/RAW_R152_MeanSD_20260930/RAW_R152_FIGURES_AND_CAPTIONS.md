# RAW 與 R152：平均位移及標準差疊圖

日期：2026-09-30。只呈現同一批30趟RAW及R152，不含其他模型。

## 平均位移與上下範圍

![RAW與R152每一步的平均位移及正負一個標準差](RAW_R152_step_mean_sd.png)

橫軸為第1至30個相鄰位移步驟，縱軸為影像量得的單步位移，單位nm，設定步距約1000nm。RAW為灰色虛線與圓點、淺灰範圍；R152為黑色實線與方點、較深灰範圍。每一點取同一步在30趟中的平均值，上下範圍為平均值減／加一個樣本標準差，每一步都有30筆，未篩選趟次、未平滑曲線。這裡使用原始影像量得的位移，沒有先扣除PI回授，也沒有事後調整R152輸出。

此圖的標準差表示「同一步在30趟重拍中的差異」。它不是單趟30步波動，也不是平均值的標準誤或信賴區間。

**英文圖說：** Mean measured adjacent-step displacement for RAW and R152 over 30 repeated scans. Lines represent the mean displacement at each of the 30 steps, and shaded bands indicate ±1 sample standard deviation across scans (n = 30 at each step). Each scan contains 31 frames and 30 adjacent displacements. The nominal step is 1 μm. No smoothing or post-reconstruction correction was applied.

[高解析PNG](RAW_R152_step_mean_sd.png) · [論文用向量PDF](RAW_R152_step_mean_sd.pdf) · [可編輯SVG](RAW_R152_step_mean_sd.svg) · [60點完整平均與上下界數值](RAW_R152_step_mean_sd_data.csv)

## 單趟30步的波動

![RAW與R152每趟30步的波動及30趟分布](RAW_R152_within_scan_sd.png)

這張圖直接保留使用者指定的單趟指標：每一點先對同一趟30個步距取樣本標準差，橫軸才是第1至30趟重拍。灰帶表示30個單趟標準差的平均值加減這30個值的樣本標準差；它是描述這批30趟的分布，不是單趟標準差的估計誤差。第一張圖的橫軸是「步」，此圖的橫軸是「趟」，兩者不能交換使用。

| 方法 | 30個單趟標準差的平均 nm | 30個單趟標準差之間的標準差 nm | 合併單趟波動 nm | 單趟波動實際範圍 nm |
|---|---:|---:|---:|---:|
| RAW | 10.062 | 1.701 | 10.200 | 6.952～13.782 |
| R152 | 4.754 | 1.051 | 4.865 | 3.377～6.989 |

R152在30/30趟都比同趟RAW波動低。單趟改善範圍36.9%～64.6%；合併改善52.3%。此合併值扣除各趟自己的平均步距後合併變異，與圖中30個單趟標準差的算術平均不同。

**英文圖說：** Within-scan displacement fluctuation for RAW and R152 over 30 repeated scans. Each point is the sample standard deviation of the 30 adjacent-step displacements within one scan. Horizontal shaded bands show the mean of the 30 scan standard deviations ±1 sample standard deviation. RAW and R152 are paired by scan.

[高解析PNG](RAW_R152_within_scan_sd.png) · [論文用向量PDF](RAW_R152_within_scan_sd.pdf) · [可編輯SVG](RAW_R152_within_scan_sd.svg) · [30趟逐趟完整數值](RAW_R152_within_scan_sd_data.csv)

## 來源與核對

來源是已完成核對的R152驗證包，共同30趟、每趟31張，兩方法各900筆相鄰位移，共1800筆。本圖保留全部30趟；前六趟曾提供RAW移動方向校準。每一個平均值與樣本標準差均以另一種計算方式逐項核對；兩方法的合併單趟波動亦與既有完整重算一致。未對圖的灰帶除以√30。

- [共同原始位移總表](../../../Experiments/R152_R148v2_SafeAdaptivePSF/results/comparison/all_displacements.csv)
- [核對結果與來源身分](figure_data_checks.json)
