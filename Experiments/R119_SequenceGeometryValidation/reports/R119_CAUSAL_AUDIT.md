# R119 causal audit and corrections

As of 2026-09-06 (Asia/Taipei). This review supersedes the causal and
"P00-P12 fully implemented" claims in the earlier R119 result/closeout notes.
Those historical files, receipts, checkpoints and training data are retained.
This turn ran diagnostic forward passes and reanalysed existing results; no
training or candidate selection was performed.

## Main finding

R119 trained successfully and has meaningful measured capability. However, its
implementation did not faithfully execute several central R118 handoff steps.
The previous inference that coherent physical sequence training caused the gains
is unsupported. Several purportedly independent controls are confounded.
File existence, passing checksums and completed receipts did not catch this.

The strongest new mechanism evidence is from one real SEM-linked exposure:
E42's normal-position correction increases contour error; suppressing only that
correction while retaining the detail path restores the original contour score.
This does not establish a universal benefit of disabling shifts. It motivates
correcting the training evidence for when/how boundaries should move.

## 1. Verified differences between the plan and training

| Planned comparison | Actual executed implementation | Consequence |
|---|---|---|
| A exactly reproduces R118 numerical/data semantics | R119 reverses distance-label signs for dark samples although the config says foreground-oriented | 2,260/5,000 training scenes have negative polarity; six sampled reversals were reproduced exactly. A is not a faithful control for the claimed R118 convention |
| B uses same-object, fixed-optics subpixel sequences | B reads the original two stored views and shares gain, offset and noise sigma; it does not read the new observation manifests | 4,534/5,000 base scenes have different a/b optical parameters. B did not perform the proposed physical sequence training |
| D is B plus targeted asymmetric optics | D takes A's independent photometry branch, then applies a native-resolution asymmetric filter | B versus D changes more than asymmetric optics; the negative result does not falsify the planned D |
| Centered asymmetric kernel | Training kernel centroid is (+1.0222, -0.1442) native pixels | OpenCV correlation moves an impulse by (-1.0222, +0.1442) pixels. This was verified numerically, so D also introduces an unaccounted coordinate offset |
| Shared development inputs/targets across arms | A and B use different photometry in their validation loaders | All 96 validation scenes differ. Mean source difference is 7.764 gray; mean target difference is 7.495 gray. Training-log scores are not directly comparable |
| Sequence/enrichment generation is verified | P05 wrote metadata manifests that the trainer never consumes | Existence of the 96/960-record manifests does not demonstrate that their observation schedule was trained |

Changing both distance sign and normal orientation can be mathematically
consistent, so the sign reversal alone is not proof that training must fail.
The verified issue is that it changed the intended control and was not declared
or tested as an independent factor.

OpenCV explicitly documents that filter2D computes correlation rather than
flipping the supplied kernel. The measured offset is consistent with that
definition: [OpenCV filter2D documentation](https://docs.opencv.org/4.13.0/d4/d86/group__imgproc__filter.html).

## 2. The earlier mechanism controls did not isolate components

In validation/path_interventions.py the neutral-width hook remains active when
the code computes the output named no_detail. That output disables BOTH width
and detail. The earlier conclusion about the effect of removing detail must be
withdrawn. In diagnostic reproduction, the incorrectly named output differs
from a true detail-only removal by up to 4.003 gray for the sampled R118 batch,
and up to 5.657 gray for sampled R119 E42.

The old attenuation control was matched to removal of normal shift, not to
each tested intervention. It cannot identify whether width-only or detail-only
effects arise from reduced correction amplitude.

New diagnostic renderers recompute each legitimate path separately, without
editing the saved model or weights. The real-image base output reproduces the
old E42 SEM reconstruction byte for byte. The copied ACM functions reproduce
all 72 saved Raw/base masks for exposure 13 exactly before comparing controls.

## 3. Direct real-sample path experiment

Population: exposure 13, all 36 matched pillars. The original SEM truth,
coordinates, cell extraction, contrast preprocessing, ACM parameters and
translation alignment were retained. Exact original helper functions were
copied into analysis/audit_sem_paths.m; this diagnostic never writes into R69.

Median boundary distance in percent of pillar pitch; lower is better:

| Output | Median boundary distance | Signed area error vs SEM (%) |
|---|---:|---:|
| Raw | 0.57719 | +5.3082 |
| Full E42 | 0.65047 | +6.0579 |
| Disable normal shift only; retain width/detail | 0.57413 | +5.3925 |
| Disable detail only; retain shift/width | 0.62443 | +5.7677 |
| Disable width only; retain shift/detail | 0.69594 | +6.4589 |
| Uniformly attenuate the full correction | 0.65444 | +6.0464 |

The attenuation factor is 0.84993. After uint8 rounding its mean correction is
3.673 gray, versus 3.582 gray for no-shift (a 2.54% mismatch); this is an
approximate amplitude control, not an exact one. Its lack of benefit supports,
but does not prove by itself, a shift-specific explanation.

This experiment implicates the position path for THIS exposure. It does not
justify disabling shifts globally, modifying deployment weights, or claiming
that the detail path is harmless in every scene. The old synthetic and new real
experiments use different checkpoints/populations and cannot be mixed into one
causal estimate.

## 4. SEM regression is a coherent area expansion

Existing 12-exposure masks were reanalysed, with float conversion before area
subtraction to prevent unsigned-integer underflow. Raw mask arrays are exactly
identical across the compared runs. The signed area error is geometric area,
not an assumption of circular pillars and not a CD replacement.

| Method | Median signed area error vs SEM (%) | Reconstructed area > Raw |
|---|---:|---:|
| Raw | +5.3424 | n/a |
| Short B probe | +4.4266 | 0/432 |
| Formal E24 | +5.4837 | 273/432 |
| Formal E36 | +5.8513 | 432/432 |
| Formal E42 | +6.1770 | 432/432 |

The drift is already visible at E24, before detail learning starts. Detail
training coincides with further expansion, but this time trend alone cannot
isolate its cause; the position/width paths and geometry also continue learning.

Pillar-paired effects, computed as within-exposure candidate-minus-Raw then
median within pillar, differ slightly from the old difference-of-medians
summary. E42 is +0.08371 pitch-percentage-points by this paired definition
(old summary: +0.08461). E24 is +0.01324 and 2/36 improving by the paired
definition, rather than the old +0.00933 and 7/36. Both definitions leave the
same qualitative conclusion. The bootstrap in the audit resamples pillars
with all exposures attached; it describes this one sample, not all samples.

## 5. Why stable centers can coexist with incorrect contours

A synthetic diagnostic expanded a centered circular edge outward by 0.4 native
pixels. Its area changed by 2.878%, while the actual training x/y readout was
approximately (-3.15e-10, -3.15e-10) pixels with confidence 0.9966.

Thus a center-position penalty has a null direction: symmetric boundary
expansion can leave the center unchanged. Per-view position consistency is
insufficient to identify every local boundary error. Existing pixel, gradient,
and distance losses do constrain such errors on their synthetic truth; their
presence does not establish that a real optical boundary matches SEM truth.

This is NOT proof that sharpness, shape and stable motion intrinsically conflict.
It shows that local edge placement and position must both be measured under
correct image formation and representative conditions.

## 6. Sequence and confirmation readout problems

- The P03 bank translates already-sampled 256px sources with bilinear
  interpolation, then applies optional blur. It is labeled pre-sampling in its
  manifest but did not replay geometry at 8x as required. Targets also remain
  at their original exposure/position in the image-error table.
- A controlled 0.4-cycle/pixel sinusoid shifted by half a pixel retained 100%
  amplitude under high-resolution physical resampling but only 30.90% under
  native bilinear translation. This is a fixture, not a measured effect for
  every microscope image; it demonstrates why the bank cannot certify the
  intended physical subpixel generalization.
- The locator calibration report says pass even though its gain/offset fixture
  returns invalid. That fixture is not included in its pass condition. A
  rank-deficient one-axis gradient is also incorrectly marked fully valid.
- The sequence summary accepts mixed scene IDs and can report 5.477px
  repeatability for two individually constant sequences with different biases.
  The existing evaluator groups correctly in this run, so this is a missing
  safeguard, not evidence that the reported groups were actually mixed.
- The stored confirmation positions are already fits against each view's own
  shifted reference. Their correct ideal value is zero. Subtracting the
  manifest inter-view displacement again produced the previous ~0.9px errors.
- Reanalysing only the saved position rows gives median residuals Raw a/b:
  0.0520/0.0568px; model a/b: 0.0508/0.0492px. The model still has one invalid
  a-view and a b-view maximum of 17.138px. The old 18.1px claim is numerically
  corrected; neither value alone proves a physical boundary moved that far.
- Confirmation did not run ACM against its available geometric truth, and did
  not include textured latent references. Image/gradient improvements there
  therefore confirm performance on those synthetic shapes, not all shape,
  motion and realistic texture goals.
- The real LSC readout itself used the historical locked path. Its reported
  confidence intervals independently resample adjacent steps within a sequence,
  contrary to the planned block-aware uncertainty analysis. Point estimates
  remain usable; do not reuse those intervals as the planned confidence proof.

Sampling sensitivity is a known issue for image networks, but general anti-
aliasing literature does not certify a particular restoration solution. The
practical implication here is to test the true observation/sampling process,
not to blur every output: [Making Convolutional Networks Shift-Invariant Again](https://proceedings.mlr.press/v97/zhang19a.html).

## 7. Evidence that still stands

On 96 fixed existing development scenes (192 identical input/target views for
all models), mean image errors in gray levels are:

| Model | Seed 1185001 | Seed 1185002 |
|---|---:|---:|
| Raw | 1.9500 | same inputs |
| Short A | 1.8122 | 1.8080 |
| Short B | 1.8246 | 1.8196 |
| Short D | 1.8351 | 1.8301 |

Formal E24/E36/E42 on those same inputs give 1.5856/1.3607/1.2384. R118 E12
gives 1.7980. B is not uniformly superior among short probes on common inputs;
the formal model nevertheless has genuine reconstruction improvements. This
diagnostic does not make the formal-vs-short training exposure equal.

For the textured-edge subset, errors go from Raw 1.75 to formal E24 1.48,
E36 1.37, E42 1.34. That gain is smaller than the global improvement. It supports
some improvement on these synthetic textures, not a demonstrated ability to
recover arbitrary real microscopic material texture.

Reanalysis of the stored locked ACM tables found E42 improves fixed-coordinate
boundary distance in 95/100 R73 and 90/100 R74 images. Under translation-only
comparison this is 87/100 and 78/100. It is not merely an average improvement
from a few outliers, but difficult cases still exist.

The four real LSC step-SD estimates (nm) are:

| Sequence | Raw | R109 | E42 |
|---|---:|---:|---:|
| 20x 0.5um | 16.777 | 13.937 | 13.447 |
| 20x 1um | 11.235 | 7.406 | 9.177 |
| 50x 0.5um | 5.380 | 3.608 | 3.591 |
| 50x 1um | 5.589 | 3.059 | 2.828 |

All four improve Raw, and three point estimates are below R109; the aggregate
deficit is concentrated in 20x 1um. The 50x 0.5um difference is tiny and should
not be called a proven win without uncertainty. Nominal motion remains a
commanded value, not independent stage truth.

## 8. Next design direction and bounded verification

Preserve the single-image local architecture as a reference while first making
the intended experiment executable and truthful. R109/R118 already introduced
separate position/width ideas; this review does not rebrand them as new.

1. Establish one explicit inner/outer geometry convention and test A byte-level
   data/forward parity. Reverse-label variants require their own declared arm.
2. Physically generate same-latent subpixel observations at 8x BEFORE sensor
   integration. Hold optics fixed for motion; vary exposure/asymmetry in
   separately labeled conditions. Consume the actual manifests in the trainer.
3. Use one frozen development input bank for all arms. Add tests that failing
   photometry/rank/grouping fixtures really fail the readout audit. Train,
   shape, registration and real LSC readouts must retain their own definitions.
4. Diagnose and supervise boundary-position correction independently from edge
   width and material detail. The new exposure-13 result prioritizes the
   position path. Extend it to all exposure conditions and 5x/20x/50x before
   designing a global change. Keep local shape supervision; do not replace it
   with center consistency or a rule forcing every shift to zero.
5. Preserve useful detail learning. Test texture-specific errors, edge midpoint,
   transition width, signed contour expansion and motion under known phases.
   A truly coherent observation bank can constrain changing boundaries without
   penalizing every high-frequency correction indiscriminately.
6. Only after these checks, run the originally intended A vs sequence-only B;
   add a centered optical-condition variant as an independent factor. The
   prior D result cannot settle that comparison. No additional training is
   authorized by the present diagnostic turn alone.

Expected benefit is a testable hypothesis, not a promised universal model.
Keep 5,000 diverse latent shapes, reuse unchanged labels, and materialize only
the affected observations. Use new independent initialization for a new round.

## Reproduction and audit trail

New diagnostics are under analysis/causal_audit_20260905:
audit.py, audit_metadata.json, audit_results.json, common_inputs_per_view.csv,
common_inputs_by_role.csv, boundary_and_sampling.py,
boundary_sampling_results.json, sem_paths.py, audit_sem_paths.m,
sem_paths/acm_paths.csv and sem_paths/acm_paths_amplitude.csv.

Protected R119 training/model source, E42 checkpoint, selection decision, base
data manifest and the already-consumed confirmation ledger were hashed before
and after the main diagnostic and were unchanged. The original receipts remain
historical records; they are not refreshed to turn semantic failures into pass.
