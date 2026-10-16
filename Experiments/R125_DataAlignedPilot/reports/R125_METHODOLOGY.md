# R125 data-to-model execution contract

## Scope and limits fixed before learned real outputs

This is a64-scene admission/end-to-end pilot, not the larger512-scene1024-update R123 study. Three arms and two starts each execute64updates. All six initial checkpoints are evaluated before the first optimizer update; only each final64-update checkpoint is compared, with no best-checkpoint search. Real microscopy/SEM and actual frame-pair outputs are primary developmental observations. Synthetic/reference checks establish data/implementation compatibility, not real usefulness.

All source/objective/model settings were frozen before initial checkpoints. Each run refuses a changed implementation or pilot configuration relative to its own initial artifact. Data files must match the admitted manifest before use. The complete input tensors, crop coordinates, original and actual-forward hashes, simulation profile, components of the objective, active modules and gradients are recorded per update.

## Why the original data could not be directly used

R118 supplied256px crops, no compatible high-density latent targets and different optics between stored views. R120 repairs physical observations only on its bank subset and still lacks the required640px context. R61 includes prior SEM/teacher sources incompatible with this source-disjoint experiment. Padding or upsampling these images would not recover missing context or remove source reuse.

The first newly generated64-scene package also failed. Direct2xmodel-vs4xobservation discrepancy exceeded the frozen RMS0.25noise-scale and p991noise-scale criteria in three corners/dense cases. A separate known-position context patch revealed a single Float32 shape-membership error. The failed package and source remain intact and are never admitted.

The revised data use8xFloat64 continuous geometry/texture and optical rendering, then area-integrated4xlatent and native targets. The model now keeps4xoptical cells while its learned prior works at2x and emits four independent phase corrections at each prior location. This adds within-cell representation capacity without quadrupling the64-channel neural feature computation. Same64seeds, shapes, motion, photometry, blur/support and noise are retained. No hard scene is dropped, no noise or blur increased to meet the screen.

All64revised scenes pass the original limits. Worst per-view discrepancy is0.09585gray RMS (0.16601times declared noise scale), p990.45748times that scale; maximum point error0.44566gray is separately reported. Declared scale includes the numerical floor and quantization variance term; it is not always the added Gaussian sigma. Six identity scenes are exact native controls. Sixteen independent8xneighborhood replays agree within0.00000760gray. These claims are limited to the simulator and do not qualify real optics.

## Training objective and units

Only `source` and the fixed per-pair simulation observation profile reach `forward_details`. The following references are used afterward, inside the same original128px center:

- Native image and4xlatent errors: stable Charbonnier distance in gray units, with0.5gray numerical smoothing.
- Native gradient-reference error: gray per native sample; both directions included.
- Observation discrepancy: half the mean squared residual divided by declared variance; the model's own explicit observation step still uses the corresponding sum-gradient with its independent curvature bound.
- Pair reference-residual consistency: `(output1-target1) - shift(output0-target0,known_delta)`. Perfect references give zero even though native interpolation is not identical to physical8xmotion. This does not independently constrain a shared absolute geometry bias; the image and geometry terms serve separate roles.
- C only: boundedSDF reference loss, balanced boundary loss and a reference-residual consistency between image and geometry. The latter subtracts each separate target representation; it does not assert SEM material boundary is always the optical half level.

The first robust-distance implementation had a tiny negative zero due subtractive cancellation; its stable algebraic equivalent `r²/(sqrt(r²+eps²)+eps)` is now exact nonnegative zero. The old function is retained. Scalar weights are in`config/pilot.json`, frozen before learned real results. They are initial engineering choices, not optimized real-performance weights.

## Data creation and controls

Categories are13 irregular-curved,13corner/line/junction,13dense-close,13textured-edge,6clean-identity and6flat. Photometry/polarity, geometry, optics, motion and sensor noise use separate random streams. Object and texture coordinates move before a single fixed within-pair PSF, sensor integration, noise and uint8quantization. SDF is foreground-positive independent of intensity polarity and explicitly a high-resolution raster approximation.

No old optical or SEM images, teacher outputs or checkpoints enter generation/training. Known synthetic PSF metadata are legitimate simulation conditions, but an independent real calibration with the same information is not available yet. The data do not fully represent coherent/phase contrast, halos, arbitrary material response, real defects or all acquisition modes.

Identity controls have pixel-aligned constant gray levels, identity optics and zero actual noise/motion; the positive observation-variance floor is merely numerical weighting. Flat examples flag motion unobservable. All supervised cores contain their declared content and avoid sensor saturation. Larger physical surroundings are generated, not padded from old smaller crops.

## Computational changes and their independent checks

Dense4xmaximum-support paired640backward is valid but took273seconds. A fixed SVD factor implementation retains the original PSF and uses the smallest stored rank whose kernelL1difference is<=1e-6. It does not refit, shift, recenter or normalize supplied optics. The implemented factor operator has an exact matching transpose up to floating-point arithmetic; it is not described as bitwise identical to the original kernel. The safe curvature bound includes approximation and arithmetic margins. CPU tests, all64kernel certificates, GPU backward and nonneutral tile tests verify this backend before candidate outputs. Worst-support backward dropped to23.53seconds in that test; real training cost varies by profile/context.

Training computes only the mathematically sufficient portion of each already-generated640px image. The same128px physical supervision remains. Context includes model dependency, the extra observation loss and pair interpolation, is determined only from fixed profile/motion, and is identical across arms. Halos80–240yield288–608px inputs, average50.9% of full area. Full versus reduced-context outputs, losses and parameter gradients were tested on actual minimum/median/maximum-support cases with a nonzero prior; maximum observed parameter-gradient relative differences were below the frozen2e-4numerical tolerance. A future halo exceeding256 is rejected, never clipped.

## Real evaluation and interpretation

Fixed inputs: six prior real images (two SEM-linked exposures plus four previews), and first two frames in the first legacy Raw-selected ROI of each of six motion suites. Same pixels, ROI/core positions, Raw motion values, SEM masks, common Raw alignment and prior readout conventions persist across all candidates. The4xreal optical profile retains the same assumed physicalGaussian as the prototype; it is not the final training scene's kernel and is not fit to candidate outputs.

All12initial/final checkpoints load exactly their learned tensors; observation buffers are intentionally excluded and rebound to the same real diagnostic operator. SEM aggregation uses Raw plus all12outputs to define a common population, with the legacy floor-sensitive crossings kept and a separately labelled sensitivity view. Motion is change relative to the same Raw pair, not absolute stage truth. No fullACM, all301frames, independent samples or verified optical-detail truth are claimed.

Small Raw phase-correlation recomputation differences(up to8.27e-8px) were separately checked at1e-6px implementation tolerance while preserving the original Raw values and exact source/ROI hashes. This is numerical replay tolerance, not a new application acceptance threshold.

No numeric application promotion boundary has been independently calibrated. The final report can describe this bounded developmental result and its failures; it cannot turn loss reduction, a small SEM-readout gain or a completion marker into production readiness or generalization proof.
