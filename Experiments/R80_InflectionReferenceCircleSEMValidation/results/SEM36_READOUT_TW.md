# R80 36顆 SEM 輪廓驗證

此資料是依 5 µm 週期重新取樣的 SEM 配對堆疊，量測比例為 5 µm / 實測週期；不可套用原生 50× 的 0.069 µm/px。

SEM、Raw與MOSR均由既有Chan–Vese ACM提供粗輪廓，再沿法線取正確極性的最大梯度轉折點。沒有使用灰階閾值。

- MOSR: 36顆pillar跨12曝光後的逐顆中位LSC直徑誤差為 84.5 nm，相對SEM輪廓徑向誤差為 42.8 nm，輪廓相關係數中位數為 0.877。
- Raw: 36顆pillar跨12曝光後的逐顆中位LSC直徑誤差為 91.8 nm，相對SEM輪廓徑向誤差為 48.4 nm，輪廓相關係數中位數為 0.557。

配對檢定：
- lsc_abs_error_nm: Raw中位數 91.785，MOSR中位數 84.477，p=2.91e-11。
- radial_shape_mae_nm: Raw中位數 48.437，MOSR中位數 42.829，p=2.91e-11。
- contour_correlation: Raw中位數 0.557，MOSR中位數 0.877，p=5.821e-11。
- mzc_roundness_abs_error_nm: Raw中位數 110.596，MOSR中位數 26.483，p=1.601e-09。
- harmonic4_abs_error_pct: Raw中位數 0.199，MOSR中位數 0.160，p=0.0556。
