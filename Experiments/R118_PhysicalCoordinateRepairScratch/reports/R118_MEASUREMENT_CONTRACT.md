# R118 next-work measurement contract

This file defines the experiments to IMPLEMENT. It does not report their
completion. Preserve these definitions across all arms.

## A. Coordinate and image conventions

- Arrays: [height, width]; model tensors: [batch, 1, height, width].
- Coordinate vector: (x, y), x right, y down, native sensor pixels.
- Positive dx translates the object right. Positive dy translates it down.
- Samples are rendered at 8x first; translation there is (8*dx, 8*dy).
- Target/source derive from the same latent scene. Blur occurs before sensor
  area integration. Noise is added after integration.
- Source/reference photometry is shared WITHIN one observation; different
  observations may have different exposure. Do not ask a single image to
  guess an unobserved canonical exposure.
- Keep float outputs for diagnostic numerics. Also export the same fixed
  np.rint(image*255) uint8 form used by the real/ACM protocol. Report both.
- Model preprocessing is fixed input scaling. No per-tile min/max normalization.
- Current distance convention is positive inside foreground; normals are the
  gradient of that SAME distance field. Do not combine it with uncorrected
  intensity-gradient normals for dark objects.
- Kernel energy sums to 1. Record its centroid and origin. Primary optical
  robustness kernels have a controlled common centroid. Pure kernel translation
  is not independently distinguishable from object translation in one image;
  put such cases in a separately labeled ambiguity diagnostic.

## B. Development sequence bank

Select 48 latent records from existing development validation using metadata:
12 families x 2 polarities x 2 records, lowest scene ID in each stratum excluding
flat_negative roles. Use the frozen next_design_selected_ids.json; do not
resample. Flat fixtures are tested separately in P02. All original roles remain
in the 512-scene training control.
No model outcomes or sealed confirmation inputs may affect selection.
One sequence keeps one latent geometry, one coordinate frame, and one declared
optical/exposure condition. Each observation has an explicit noise seed.

Per latent geometry:

| Protocol | Positions | Repeats/condition | What stays fixed |
|---|---|---|---|
| static_repeat | (0,0) | 8 independent noises | geometry, optics, exposure |
| motion_x | dx = -1 + 0.125*k, dy=0; k=0..16 | 1 each | geometry, optics, exposure |
| motion_y | dx=0, dy = -1 + 0.125*k; k=0..16 | 1 each | geometry, optics, exposure |
| motion_diag | dx=dy=-1+0.125*k; k=0..16 | 1 each | geometry, optics, exposure |
| exposure_static | (0,0), exposure gains 0.7/0.85/1/1.15/1.3 | 4 noises each | geometry, optics |
| blur_static | (0,0), three recorded blur conditions | 4 noises each | geometry, exposure |

This is 91 observations per latent, 4,368 observations total before any explicitly
declared invalid-crop exclusions. The three blur conditions are baseline
isotropic, rotated anisotropic, and a centered asymmetric-tail kernel. Their
exact parameters are written to the bank manifest BEFORE model evaluation.

Use a common fixed interior ROI for comparison. If an object is clipped, do
not use the visible-mask centroid as if it were the full-object position.
Record that locator as inapplicable; an image-registration readout can remain
valid if its reference support stays inside the common ROI.

### Required bank record

```json
{
  "schema_version": 1,
  "scene_id": "dev_<existing_scene_index>",
  "sequence_id": "dev_<id>_motion_x_condition00",
  "condition_id": "condition00",
  "protocol": "motion_x",
  "frame_index": 0,
  "family": "ellipse",
  "polarity": -1,
  "split": "development",
  "true_x_px": -1.0,
  "true_y_px": 0.0,
  "noise_seed": 0,
  "kernel_id": "kernel00",
  "exposure_gain": 1.0,
  "source": "<relative-array-path>",
  "reference": "<relative-array-path>",
  "mask": "<relative-array-path>",
  "sdf": "<relative-array-path>",
  "source_sha256": "<measured hash>",
  "reference_sha256": "<measured hash>",
  "complete_object_in_roi": true
}
```

The illustrative noise seed/hash/path above MUST be replaced by actual values.
Store kernel definitions/centroids in the manifest rather than filenames.
Use separate train-bank IDs and development-bank IDs. Never split frames from
one latent scene between training and validation.

## C. Separate the quantities

For estimated position p_hat[k] and known true p[k]:

- Position error: e[k] = p_hat[k] - p[k].
- Fixed sequence bias: mean_k(e[k]); report x and y, not only magnitude.
- Static repeatability: sample SD of e[k] for the SAME scene, SAME condition,
  SAME true position, independent noise repetitions; ddof=1.
- Motion step error:
  (p_hat[k+1]-p_hat[k]) - (p[k+1]-p[k]).
- Motion step bias: mean of step error within one sequence.
- Motion fluctuation: sample SD of step error within one sequence.
- Tail: 95th percentile of absolute step error, plus worst valid step and
  explicit failure count. Do not discard difficult but valid samples.
- Cross-axis error: orthogonal coordinate error for x-only/y-only motion.
- Nuisance sensitivity: change of e relative to that scene's nominal
  condition; report exposure and blur separately.

First compute these PER sequence/condition. Then summarize across scenes
using median and distribution. Do not compute one SD across different shapes
and call it sequence repeatability. Do not subtract a new alignment separately
from every frame; that would erase the displacement being tested.

Absolute scale in um/nm comes ONLY from the relevant locked sequence config.
Current 50x object_um_per_px is 0.069 in that protocol. Do not substitute a
project-wide remembered 0.1725 value or assume every dataset shares a scale.

## D. Readouts and calibration

1. Keep the R118 training x/y fit as a DIAGNOSTIC readout.
2. Add an independent image-registration readout for the synthetic bank,
   using the same fixed reference/support and photometry treatment for every
   model. Use subpixel fitting, not integer peak alone.
3. For shape masks, report translation from the fixed reference contour and
   shape errors separately. An ACM mask centroid is applicable only to a
   complete object; no circular assumption is imposed on arbitrary shapes.
4. Real pillar motion uses the existing locked ACM-inflection-LSC protocol,
   with shared Raw-selected frames/identities and unchanged parameters.

Before evaluating a model, calibrate every readout on:

- Exact identity image: zero displacement within numerical tolerance.
- Known +/-1px x and y shifts and +/-0.5px diagonal shifts of a fully visible
  analytic shape. The existing local-fit fixture tolerance is 0.08px; record
  observed errors, not only a pass flag.
- Gain/bias-only photometric changes at fixed geometry.
- Symmetric width/blur changes at fixed center.
- Bright/dark complements under a consistent coordinate convention.
- Flat/empty/rank-deficient images: explicit invalid or unobservable-axis
  flag, never a fabricated perfect zero measurement.
- Cropped objects and wrong-sign/axis sentinels: they must be detected.

If a readout invents motion under a center-preserving transformation, diagnose
the estimator before changing model training to please it. A test tolerance
may change only with a written resolution/noise justification and a new
protocol ID applied to ALL comparison methods.

## E. Shape and detail

ACM primary shape results: per-image mean boundary distance, HD95, overlap,
area error, perimeter error, and complete failure counts. Preserve both fixed
pixel coordinates and translation-only comparisons where the locked protocol
requires them. Translation-only shape agreement does not prove position accuracy.

Detail: report error/correlation relative to known target gradients/frequency
content, edge transition width, overshoot/ringing, and signed difference maps.
Raw high-frequency energy alone mixes texture with noise. Target visibility
weighting must attenuate the numerator of the actual error, not normalize
itself away. Keep flat-target denoising supervision.

Real Raw previews: 5x, 20x, 50x, and center-nine crops. Display the same
intensity range and crop for every method, with labels Raw / method / difference.
Never use a difference panel's rings as direct proof of visible output rings;
inspect the reconstructed image and edge profile itself.

## F. Required tables

positions.csv key: (method, sequence_id, frame_index, feature_id, estimator).
Columns: scene_id, family, protocol, condition_id, true_x_px, true_y_px,
estimated_x_px, estimated_y_px, valid, failure_reason, source_sha256.

steps.csv key: (method, sequence_id, start_frame, end_frame, feature_id, estimator).
Columns: true_dx_px, true_dy_px, measured_dx_px, measured_dy_px, error_dx_px,
error_dy_px, valid, failure_reason.

sequence_summary.csv key: (method, sequence_id, estimator).
Columns: scene_id, condition_id, protocol, valid_count, failure_count,
bias_x_px, bias_y_px, repeat_sd_x_px, repeat_sd_y_px, step_sd_x_px,
step_sd_y_px, step_p95_abs_x_px, step_p95_abs_y_px, cross_axis_error_px.
Use null with an explicit not-applicable reason for nonmatching protocols.

shape_detail.csv key: (method, scene_id, condition_id, frame_index).
Columns: boundary_distance_px, hd95_px, iou, perimeter_error_pct,
reference_gradient_error, transition_width_px, ring_measure,
acm_valid, failure_reason. Document exact definitions beside the table.

Audit tables must list expected/observed rows, duplicate keys, missing
conditions, nonfinite values, and each exclusion with its model-independent reason.

## G. Aggregation and uncertainty

- Synthetic independent unit: latent scene. Frames/conditions are repeated
  observations, not new independent samples.
- SEM independent unit: physical pillar, n=36. Twelve exposures are repeated.
- Real sequence adjacent steps share frames. Do not treat them as independent
  in a naive bootstrap. Use scene-level resampling for synthetic groups and
  sequence-aware/block resampling when estimating step uncertainty.
- Report paired candidate-minus-control effects using the same scene IDs.
  Record seeds, resampling count, block length, and sensitivity to block length.
- Default diagnostic resampling: 2,000 replicates, seed 1199001, paired 95%
  percentile intervals. For synthetic effects resample latent scenes, retaining
  all their repeated observations. For real steps retain acquisition ordering
  and all nine pillars together per sampled frame block; never treat pillars
  from one frame as independent camera repetitions. Use block length 5 with
  sensitivity at 3/7; break blocks at acquisition gaps in the selected pairs.
  If too few contiguous blocks remain, report descriptive uncertainty instead
  of manufacturing a confident interval. SEM resamples pillars with all
  exposures attached. These intervals characterize this population, not every
  possible future microscope/sample.
- A single pooled threshold or single favorable average cannot erase
  a failing family. Do not combine unlike units into a winner score.

## H. Historical protocol boundaries

The repository's 720-angle rule applies to the historical
run_sequence_analysis.py path documented in QUIRKS.md. The existing locked
LSC path uses sample_count=64 at 20x and 96 at 50x. Do not silently change those
to 720 while retaining old baseline numbers. A protocol change requires a
versioned all-method rerun.

R118 helper location_xy is NOT the real LSC program. Legacy CUA/GMF software
is unnecessary for this thesis plan. Do not request a new external GMF key.
