> **讀值待依修正版引用：** 原稿讀法發現順序依賴，此處原圖保留；更新數字與新舊模型比較請見[位移稽核](../../reports/R152_DISPLACEMENT_AUDIT.md)。

# IMPACT2026 R152 poster text

## Title

Measurement-Oriented Microscopy Reconstruction for Cross-Magnification Micro-Displacement Inspection

## Experiment identification

R152 follow-up evaluation using the original four conditions and 120 locked pairs. The learned weights are fixed. R152 uses its native 25-kernel optical bank at 20x and the original calibrated single PSF through an inference input adapter at 50x. This is the current main result; the shared-bank run is supplementary.

## Motivation

Sharper microscopic images do not necessarily give more stable position measurements. Reconstruction should therefore be assessed through a common measurement procedure, with the same images and feature identities held fixed.

## Method

The delivered R152 weights were used without retraining. Its frozen reconstruction path combines image context and bounded native-grid corrections, followed by a bounded Fourier optical correction. At 20x, the original 25-PSF bank was retained. At 50x, an optional and reversible inference-only adapter installed the original measured 50x PSF in both optical paths. With one calibrated kernel, the optical weight is exactly one; no multi-PSF selection is claimed at 50x. Learned neural parameters and output correction strengths were unchanged. Removing the temporary optical input restores native 25-PSF inference.

Raw, fixed Wiener and R152 were measured by the original common backend: coarse active contour, correct-polarity maximum-gradient boundary refinement, and geometric least-squares circle center. The absolute median horizontal shift of nine pillars defines the array step. Native coordinates are converted using 0.1725 and 0.0690 micrometers per pixel for 20x and 50x, respectively.

## Experiment

The four conditions combine 20x and 50x objectives with nominal 0.5 and 1.0 micrometer steps. Thirty original adjacent-frame pairs per condition were retained: 120 pairs from 166 distinct frames. Pair identities, nine pillar identities, localization windows, intensity polarity and measurement settings were fixed. Wiener retained the original objective-specific calibration and fixed regularization.

## Main results

Across the 120 original pairs, R152 yielded Step SD of 7.13 nm, nominal MAE of 5.54 nm, and median within-grid SD of 4.35 nm. All four condition-level results are retained; very small numerical differences are not treated as proof of practical superiority.

| Scope | Method | Pairs | Step SD (nm) | Nominal MAE (nm) | Median within-grid SD (nm) |
|---|---|---:|---:|---:|---:|
| all120 | Raw | 120 | 8.884944 | 7.001601 | 12.547376 |
| all120 | Wiener | 120 | 7.906361 | 6.417996 | 5.983640 |
| all120 | R152 | 120 | 7.125267 | 5.542029 | 4.353063 |

## Metric definitions

Step SD is the mean of the four condition-level sample standard deviations. Nominal MAE is the mean of the four condition-level mean absolute deviations from the nominal step. Median within-grid SD is the median of the 120 pair-level sample standard deviations of the nine signed horizontal pillar shifts. The three criteria are reported separately.

## Interpretation and limits

The results evaluate this specimen and these four acquisition conditions. Agreement with nominal stage steps is not independent absolute length accuracy. Adjacent pairs can share frames; paired resampling intervals are conditional on the original selected pairs. The single calibrated 50x PSF does not establish spatially adaptive PSF selection at 50x, and this experiment alone does not establish a universal model across specimens, objectives or devices.

## Figure captions

**Figure 1. Measurement protocol.** Original four-condition, 120-pair evaluation with fixed learned R152 weights, native 20x optical information and the original single calibrated 50x PSF. All image methods share one boundary-and-center measurement backend.

**Figure 2. Aggregate displacement results.** Step SD and nominal MAE are means of four condition-level values; median within-grid SD is the median of 120 pair-level nine-pillar standard deviations. Values are in nanometers and lower is better.

**Figure 3. Condition-level results.** All three metrics are shown separately for the original 50x/0.5, 50x/1.0, 20x/0.5 and 20x/1.0 micrometer conditions, each with 30 locked pairs. No condition has been excluded.

**Figure 4. Representative outputs.** The start frame of the first locked pair in each condition is shown for all methods at the same 0–1 display range. Scale bars are 2 micrometers. Images were selected by original pair order, not reconstruction quality; quantitative measurements use the original numeric outputs.

## 中文交付說明

主結果採用各倍率對應的光學資料。R152沒有重訓；只在50×增加能讀入原單顆校正資料的入口。完整數據、正負結果、原配對及共用光學資料的附加比較均保留。此素材可用於本輪海報，但不要將原投稿V42的數字或元件效果直接套在R152上。
