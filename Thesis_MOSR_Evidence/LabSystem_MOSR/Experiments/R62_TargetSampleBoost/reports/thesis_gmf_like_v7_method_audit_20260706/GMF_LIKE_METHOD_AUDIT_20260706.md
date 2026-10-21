# GMF-like method audit for thesis displacement data

## What changed in this turn

- Added an open in-repo GMF-like Gaussian template displacement tool.
- Verified it on synthetic subpixel motion with pytest.
- Found that polarity and ROI choice are decisive: using dark polarity on bright-hole regions gives misleading results.
- Corrected 100MG to use the cleaner top-right dark pillar array.
- Tested a smaller bright-grid ROI for the 20x/5x sample to avoid the slow, over-broad ROI.

## Valid same-ROI comparisons

| group | ROI strategy | best | Raw std um | R61 std um | V7 std um | V7 vs Raw | V7 vs R61 |
|---|---|---|---:|---:|---:|---:|---:|
| x_0p5um | top_right_dark_pillar_array | raw | 0.00619 | 0.00623 | 0.00630 | 1.8% | 1.1% |
| x_1um | top_right_dark_pillar_array | v7 | 0.01267 | 0.01288 | 0.01267 | -0.0% | -1.7% |
| 20x_0p5um | small_bright_dot_grid_radius10 | raw | 0.04008 | 0.16081 | 0.15661 | 290.8% | -2.6% |
| 20x_1um | small_bright_dot_grid_radius10 | raw | 0.03493 | 0.04389 | 0.04536 | 29.9% | 3.3% |
| 5x_0p5um | small_bright_dot_grid_radius10 | raw | 0.04817 | 0.10417 | 0.09994 | 107.5% | -4.1% |

## Interpretation

- The GMF-like route is viable, but it is not yet a locked thesis metric.
- With corrected 100MG ROI, V7 is essentially tied with Raw/R61 at 1um and slightly worse at 0.5um.
- With the small bright-grid ROI, V7 does not show a broad stability win on 20x/5x; several reconstructed cases lose tracked features, which is itself a useful failure signal.
- This suggests the next training target should not simply sharpen images. It should preserve local fitted-feature consistency so that the same physical features remain trackable after reconstruction.

## Next training implication

- Add GMF-like/localization validation as a selection metric for future R62/R63 runs.
- Create training examples that penalize feature disappearance or local center drift after reconstruction.
- Keep the old edge/sequence losses because they still protect global structure, but add a local fitted-anchor guard for thesis ROI behavior.

## Files

- Tool: `D:\GMM_2_Final\Tools\Displacement_Algorithms\scripts\measure_gmf_template.py`
- Tests: `D:\GMM_2_Final\Tools\Displacement_Algorithms\tests\test_measure_gmf_template.py`
- Compact audit table: `gmf_like_method_audit_compact.csv`
- Valid comparison table: `gmf_like_method_audit_valid_comparison.csv`
