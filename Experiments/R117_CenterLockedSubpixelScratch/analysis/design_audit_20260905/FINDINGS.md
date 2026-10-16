# Design-direction audit, 2026-09-05

This is a diagnostic review, not a repaired model or a new training run. The
original R117 training code, configuration, data manifest, and final weights
were read and left unchanged. Executable diagnostics and their outputs are in
this directory.

## Answer

The intended goals are coherent: single-image restoration, accurate geometry,
stable localization, recoverable detail, and tiled deployment. However, the
project repeatedly promoted plausible constraints into architectural guarantees
without testing their actual coordinate conventions, gradients, or reachable
outputs. Several previously diagnosed data and training problems persisted.
The present evidence does not show that the project has reached a fundamental
information or model-capacity ceiling.

## New executed evidence

1. **Preview provenance is wrong.** All four R117 real-preview inputs point to
   R109 output files whose names still end in `raw.bmp`. Re-running R109 E48
   from its actual inputs reproduces these four files exactly, pixel for pixel.
   The intended direct R117 pipeline was therefore evaluated visually as
   R109 followed by R117. R109-vs-input changes are 3.405 gray at 20x, 4.647 at
   50x, and 2.621 on the center-nine crop. Direct R117 previews are now saved
   separately. Direct R117 still shows an inner ring, but less strongly than
   the cascade. This invalidates the earlier attribution of the entire preview
   artifact to direct single-pass R117; it does not invalidate separate
   R116/R109 ACM or motion runs that read their own correct input paths.

2. **Geometry and photometric normals disagree on polarity.** The generator
   defines positive SDF inside foreground, while the model obtains normals
   from increasing image intensity. These directions reverse on dark objects,
   yet the profile and reflection use `-sdf * normal` without a polarity
   adjustment. On an exact straight boundary, x=4 samples center x=8 rather
   than 0, and reflects to x=12 rather than -4. In 72 balanced diagnostic
   scenes (12 families, 3 per polarity), the mean wrong-normal fraction on
   dark boundaries is 97.76%. Supplying true SDF, its sample-to-boundary mean
   error is 4.080 px; changing only the sign with oracle geometry reduces it
   to 0.192 px. These numbers diagnose sampling, not final image accuracy.

3. **The location consistency loss does not train the location estimator.**
   During the paired stages only width or shift parameters are active. The
   SDF pair term has `requires_grad=False` and exactly zero gradient to both
   groups. All 42 detector tensors are bit-identical between E6 and E42.
   Its logged value around 2 is therefore not evidence of geometry learning.
   The final detail stages also omit pair training and only log the contour
   term; contour is not included in the final detail objective. Pixel/gradient
   reconstruction still provides some indirect geometric supervision.

4. **The named center loss is not an x/y displacement loss.** It averages
   signed distance weighted by gradient magnitude around the whole object.
   Opposite sides cancel when a shape translates. A known 1px displacement
   of a circle produces only 0.001380 change in this loss; 2px gives 0.006957.
   It is more sensitive to radial shrink/expand bias than to true translation.
   The actual x/y centroid term is computed and logged but is not added to
   width, shift, or detail losses.

5. **The targets conflict with the allowed operations.** In the 72-scene
   diagnostic, an average 66.52% of tested boundary pixels request a width
   gain greater than even the theoretical maximum permitted by the frozen
   detector/support, with the action confidence set to one. The same scene
   has independently blurred views but their correction gains are penalized
   for being different. Even the generated ideal gain maps disagree by a
   boundary-weighted mean 0.801. Correction parameters should be allowed to
   differ when the degradation differs; restored geometry should agree.

6. **A discontinuity exists at neutral width gain.** In the native width
   formula, a pixel outside its sampled endpoint range is restored exactly
   at gain=1 by a special correction. At gain=1.000001 it is clipped toward
   the endpoint range. A scalar counterexample jumps by 15.351 gray for a
   0.4 width gate. On the four real inputs, 25.9–61.3% of pixels with width
   gate above 0.1 lie outside the endpoint range. The prevalence check is
   diagnostic and is not a deployment threshold. Correcting only this
   discontinuity in frozen inference does not remove the pillar ring.

7. **Center projection itself is implicated in the ring.** On the true Raw
   center-nine crop, keeping all learned weights fixed and bypassing only
   the center projection drops the radial inward reversal measure from
   0.394 gray to 0.0038 gray; the Raw measure is zero. Correcting only normal
   sign reduces it to 0.182 gray. The final image can therefore develop rings
   through the purported protection operation. These single-crop frozen
   interventions are not proof of an improved deployable model.

8. **Dataset diversity by record count is misleading.** A fresh full scan of
   the 5,000 training scenes found 379 dense arrays (7.58% of scenes) supplying
   74.06% of boundary pixels and 54.96% of the implemented SDF loss weight.
   Effective clear/identity supervision is 39.55% of the three-view stream.
   These are not automatically bad percentages, but the large imbalance was
   already diagnosed in R113 and was not controlled in the final R117.

9. **Metric names encouraged overinterpretation.** R117's per-epoch contour
   score is soft threshold Dice, not the locked ACM algorithm. The horizontal
   gradient energy difference is not a sharpness or texture-fidelity metric.
   In the new 72-scene diagnostic, error against true gradients decreases
   17.47% even though energy decreases. The target image itself averages
   only 0.882 soft Dice (bright 0.968, dark 0.796), so the image and geometric
   targets are not mutually exact under that threshold. This alone is not a
   proof that labels are wrong; it demonstrates that one metric is not a
   direct measure of the desired shape.

10. **Some progress is real.** Boundary discrimination is alive in R117:
    mean AUC 0.931 and median 0.988 on this diagnostic set. Unlike R109's
    previously documented dead boundary branch, R117 is not wholly inactive.
    Boundary SDF error is still about 2.10px in the selected band, so it is
    not yet a sufficiently precise coordinate system for aggressive rendering.
    Its final data/weights/checkpoints remain useful controlled evidence.

11. **Earlier intervention conclusions were stronger than their design.**
    The E42 center-locked arm adds reflection and another high-pass/bounding
    cycle to an already bounded residual, without an amplitude-matched
    attenuation control. The guarded arm also applies this projection. The
    no-shift arm reuses detail constructed from the shifted anchor. These
    frozen ablations establish sensitivity of a co-adapted checkpoint, not
    the necessity of a path for every scratch architecture or proof that
    center locking will improve a newly trained model. The measured LSC
    degradation in the center-locked arm remained an unresolved negative
    result when the subsequent full run was launched.

## Historical reconciliation

- R109 E48 actual locked tables reproduce R73 0.2846993 -> 0.1658165 and
  R74 7.2417585 -> 2.498933 (respectively 41.76% and 65.49% reductions in the
  median per-image boundary-distance metric). SEM per-pillar median is
  0.569703 -> 0.534464 percent of pitch (6.19% reduction).
- R109 R73/R74 tables retain the old literal method label `R61v16`. Their
  experiment config, inference manifest, R109 checkpoint manifest, and
  reconstruction program identify them as R109 E48. Do not compare by the
  table label alone. This is a provenance/documentation defect.
- R116 E42 retains SEM coarse-boundary improvement but R74 aggregate
  boundary worsens 4.28%, and thesis LSC step SD is 8.067nm versus R109
  7.003nm and Raw 9.745nm. It is not a uniformly better successor.
- R101 and R103 already documented high-frequency target incoherence,
  radiometry ambiguity, and gradient imbalance. R113 documented dense-array
  edge-mass dominance, clear-pair dominance, and limited renderer capacity.
  R117 reuses the basic generator family and again adds a clear view per
  scene. Its degradations still operate after low-resolution target creation;
  high-resolution label translation is real, but it is not a complete
  continuous optical image-formation model.
- R117 removes R116 tangent-coherence operations without a matched isolation
  test; it changes data, rendering, supervision, and training schedule at once.
  Its 2x branch predicts geometry and averages it down; it does not render the
  final grayscale restoration on the higher-resolution grid.

## Interpretation and next design principles

Use R109 as a functional reference, not a teacher or inherited checkpoint.
Keep single-image input, pure synthetic geometry, antialiased labels, and
local tiled computation. Rebuild the coordinate/action interface so its sign,
units, neutral behavior, and valid sampling are correct for both polarities,
corners, thin gaps, and textures. Coordinate loss must measure actual x/y
movement and reach trainable coordinate parameters. Train consistency on
restored quantities, not equal correction amounts under unequal blur.

Define targets as a common reference optical image from one latent scene.
Calibrate optical/noise statistics without copying SEM structures. Distinguish
recoverable texture from erased information. Balance by boundary evidence and
shape complexity as well as scene count. Restore texture and geometry through
operations whose useful output family has been checked using known truth;
bounded high-pass evidence alone does not guarantee absence of hallucinations
or ringing. Full-image low-frequency preservation inherited from the GMF
objective should be re-justified against the thesis objective.

Evaluate learned mechanisms with continuous and subpixel test inputs, compare
against Raw and the working R109 renderer, and use a matched one-change
comparison before another full training run. The already repeatedly consulted
R73/R74/SEM populations are development evaluations, not unseen confirmation
sets. Preserve an untouched confirmation set for final claims.

## Limits

The new sampling diagnostic uses known geometry to isolate implementation
errors; the oracle sign is unavailable as such at deployment. A zero-gradient
finding and checkpoint equality prove a missing training path, not its exact
share of final image error. No claim is made that repairing these defects
alone will beat R109 or solve all optical conditions. Single-image data can
leave several physically plausible high-frequency structures indistinguishable.
The present failures are not evidence that the project is already at that limit.

Primary theory references: Weigert et al., Nature Methods (2018),
https://www.nature.com/articles/s41592-018-0216-7;
Zhang, ICML (2019), https://proceedings.mlr.press/v97/zhang19a.html;
Blau and Michaeli, CVPR (2018),
https://openaccess.thecvf.com/content_cvpr_2018/html/Blau_The_Perception-Distortion_Tradeoff_CVPR_2018_paper.html.
The last paper does not establish an unavoidable conflict between geometric
accuracy and displacement stability.
