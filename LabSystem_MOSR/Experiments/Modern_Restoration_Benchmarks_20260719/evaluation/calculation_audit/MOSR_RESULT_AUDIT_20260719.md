# MOSR Result Audit and Defensible Positioning

## Executive conclusion

The saved CD, sharpness, displacement, line-width, SEM conversion, and throughput aggregates reproduce from the underlying row-level data. The principal issues are not arithmetic mistakes. They are the interpretation of the motion reference, the Raw-ranked 30-step selection rule, and the mixed direct-versus-tiled runtime comparison.

MOSR should not be positioned as the winner of every metric. The strongest defensible thesis position is that MOSR preserves measurement geometry while improving boundary observability, gives robust pillar localization tails, and remains deployable on a native full field of view. This is a stronger measurement-oriented claim than saying only that the image is visually sharp.

## Results that most strongly support MOSR

| Evidence | MOSR result | Best defensible interpretation |
|---|---:|---|
| 50x pillar CD midpoint MAE | 48.6 nm | Essentially preserves the Raw CD result (46.3 nm) while narrowing threshold sensitivity |
| 50x pillar CD interval width | 81.8 nm | 71.4% narrower than Raw, indicating more stable boundary placement across 35%-65% thresholds |
| 50x pillar edge width | 508.9 nm | 17.1% lower than Raw without the large CD shift of the visually sharpest baselines |
| 50x pillar ringing ratio | 0.00465 | 62.9% lower than Raw and lower than all learned comparators in this condition |
| Pillar formal p95 absolute step error | 17.94 nm | Best tail result among the five methods on the stable-step subset |
| Pillar all-within-session median absolute error | 5.53 nm | Best robust center among learned methods under the non-ranked sensitivity audit |
| Pillar all-within-session p95 absolute error | 28.16 nm | Best robust tail among learned methods under the non-ranked sensitivity audit |
| 20x via CD midpoint MAE | 224.2 nm | 65.2% lower than Raw and best among the compared methods, but must be paired with the ringing warning |
| 20x via edge width | 180.9 nm | 79.6% lower than Raw and best among the compared methods |
| Formal full-frame deployment latency | 408.0 ms | Practical end-to-end latency when MOSR is allowed to run directly on the full frame; not intrinsic architecture speed |

## Findings that limit an unrestricted “MOSR is best” claim

- Base U-Net has the lowest formal pillar mean absolute step error (5.92 nm versus MOSR 6.40 nm) and the lowest within-grid inconsistency.
- On the same 118 formal pillar steps, MOSR differs from Base U-Net by +0.49 nm mean absolute error (paired Wilcoxon p=0.064) and from EDSR by +0.26 nm (p=0.287). These results support statistical comparability, not MOSR superiority on mean error.
- EDSR or Base U-Net is better than MOSR on the via displacement mean error metrics.
- EDSR and Raw are better than MOSR on the line-displacement result. The line experiment supports morphology transfer, not MOSR dominance.
- MOSR has severe 20x via annular ringing (mean ratio 0.581). The outer boundary is closer to SEM, but the restored morphology is not uniformly faithful.
- MOSR is not faster than Base U-Net when both receive the same input representation. It is 61.8% slower on a 256x256 patch, 17.1% slower on a direct 2048x1536 frame, and 23.6% slower under the same tiled path.

## Calculation audit

| Item | Audit result | Interpretation |
|---|---|---|
| CD interval and summary arithmetic | Pass; maximum reproduction difference below 1e-9 nm | Saved values are reproducible |
| Displacement statistics | Pass; maximum reproduction difference below 1e-9 nm | MAE, RMSE, SD, median, p95, and within-grid calculations are correct |
| Line-displacement statistics | Pass; maximum reproduction difference below 1e-9 nm | Saved pooled and per-sequence values are reproducible |
| SEM conversion | Pass | Pillar and via workbook values are treated as radii and doubled for diameter |
| 20x/50x SEM orientation | Pass | Both magnifications use the same nine physical SEM values after their recorded image transforms |
| Pixel scale formula | Pass with calibration caveat | 3.45 um / magnification gives 0.069 and 0.1725 um/px; no independent effective-magnification calibration is included |
| 30-step selection | Formula reproduced exactly | The score is Raw deviation from nominal motion, so the subset is Raw-favorable by construction |
| Motion reference | Incomplete evidence | Current evaluation files contain nominal commands, not numeric per-frame PI feedback |
| Runtime throughput | Pass with comparison caveat | Original latency is practical pipeline latency, not equal-input model speed |

## Runtime explanation

The original deployment run gave MOSR one direct 2048x1536 inference. Base U-Net, NAFNet, and EDSR were evaluated through 256x256 overlapping tiles. A 2048x1536 frame contains 3.15 megapixels, but the overlapping tiled path processes 192 tiles, or 12.58 megapixels before overlap fusion, plus tile assembly. This is why MOSR appeared faster than Base U-Net in the original chart.

Under equal-input timing, the ranking changes:

| Model | 256x256 patch median | Direct full-frame median | Same tiled path median | Direct peak GPU memory |
|---|---:|---:|---:|---:|
| NAFNet | 9.54 ms | 152.74 ms | 659.78 ms | 1,992 MB |
| Base U-Net | 8.10 ms | 341.93 ms | 888.97 ms | 5,069 MB |
| MOSR | 13.11 ms | 400.23 ms | 1,099.03 ms | 5,466 MB |
| EDSR | 20.27 ms | 915.59 ms | 3,753.14 ms | 3,521 MB |

Therefore, the correct claim is: MOSR supports a convenient native full-frame deployment path and achieves 408 ms end-to-end latency in the formal configuration. The incorrect claim is: MOSR is intrinsically faster than Base U-Net.

## How to make the MOSR case stronger without cherry-picking

1. Use a controlled translation-equivalence experiment as the primary innovation test. Apply known subpixel translations to the same measured image and compare whether each reconstruction preserves the imposed boundary shift. This directly tests position preservation without stage-command uncertainty.
2. Predeclare shift magnitudes, phases, directions, metrics, and rejection rules. Report median error, p95 error, failure rate, and within-feature spread rather than choosing only the best mean.
3. Present threshold sensitivity as a 35%-65% interval or curve. Do not rely on a single 50% threshold or a post-hoc weighted score.
4. Separate three claims: measurement fidelity (CD), localization stability (shift), and practical deployment (latency). Do not combine them into an arbitrary overall score.
5. Use 50x pillar as the main balanced-measurement example, 20x via as a difficult recovery example with an explicit ringing guardrail, and pillar all-within-session as the robustness check.
6. If the numeric PI feedback log exists, join it by frame and recompute every displacement metric against that feedback. This is the most important reference-quality improvement.

## Recommended thesis wording

“MOSR did not obtain the lowest mean error in every object and imaging condition. Its advantage was most evident in preserving measurement geometry while reducing boundary ambiguity. For the 50x pillar region, MOSR retained a CD error close to the Raw measurement but reduced the threshold-dependent CD interval by 71.4% and reduced the radial ringing index by 62.9%. In the pillar displacement audit, MOSR also produced the lowest p95 error on the formal stable-step subset and the lowest median and p95 errors among learned methods when all valid within-session pairs were considered. These results support robust boundary localization rather than unrestricted visual-sharpness dominance.”

## Source files

- Row-level and aggregate CD results: `evaluation/circular_cd_sharpness/`
- Row-level and aggregate displacement results: `evaluation/displacement/`
- Line-width transfer results: `evaluation/line/tables/`
- Step-selection sensitivity: `evaluation/selection_sensitivity/` and `evaluation/line_selection_sensitivity/`
- Equal-input runtime audit: `evaluation/runtime_fair_modes/`
- Machine-readable calculation audit: `evaluation/calculation_audit/CALCULATION_AUDIT.json`
- Paired formal displacement comparisons: `evaluation/calculation_audit/FORMAL_PAIRED_COMPARISONS.csv`
