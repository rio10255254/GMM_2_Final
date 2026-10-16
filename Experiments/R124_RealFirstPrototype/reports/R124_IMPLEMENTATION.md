# R124 implementation contract

## Actual computation

`PrototypeModel` receives normalized FP32 grayscale NCHW images. The sole latent image state has twice the native cell density. Initialization repeats each native average into its cells, while output is their exact area average. There is no claim of doubled physical resolution.

The shared prior receives seven channels: latent state, lifted input, lifted current observation residual, fixed local Raw x/y differences, calibrated noise scalar, and gain scalar. It has64 channels and four two-convolution residual blocks with dilations1/2/4/2. The final prior convolution starts at zero; the lower layers are trainable. No stride/downsample phase, global spatial statistics, attention or FFT is used.

Each of four steps records:

1. State and predicted observation before the update.
2. Learned bounded prior correction and proposed state.
3. Observation of that proposal and explicit negative-gradient correction.
4. Separate projection to the normalized optical-intensity interval[0,1].
5. State and native output after the step.

The projection is an explicit implementation refinement to R123, not a claim of observation evidence or a hidden final detail patch. The quadratic-proximity term identified as inactive during R123 design is absent. Step fractions are constrained below the independently bounded observation curvature limit. The observation loss underlying this step is a **sum**, not a mean dependent on tile size. Reported training losses may be normalized later only if their actual gradient scaling is separately specified.

The shared prior's zero initialization means current real Gaussian-profile image changes come from the assumed observation corrections and projection, not learned reconstruction. Nonzero prior weights are deliberately exercised only in numerical stress tests; no stressed state is promoted or saved as a learned model.

## Observation operator

The low-level fixed affine operator is `F(x)=a*P(Kx)+b` with positive constant calibrated gain and variance, finite nonnegative normalized kernel, and zero extension. It never automatically renormalizes, recenters or trains the supplied kernel. The constructor rejects invalid norms, dimensions, factors, radiometry, variance and support. Internal dimensions must divide exactly by sampling factor; broadcasting or silent cropped integration is refused.

PyTorch's K implementation is correlation. The loader requires a convention: a physical impulse-response PSF is flipped once before construction; an explicitly supplied correlation kernel is kept as-is. Array centroid and resulting impulse displacement are exposed. Asymmetric impulse, independent scalar loops, transpose inner products, dense Hessians, automatic gradients and finite differences test this distinction.

For the declared finite zero-boundary linear operator and area average, the curvature upper bound is `a²||K||₁²/(s² variance)`, with a floating-point margin. Constant bias is not part of the adjoint. Noise weighting has a finite positive variance, not an output-derived learned confidence. This bound is not automatically valid for a future reflective/nonlinear/saturated operator; those cases need an independently tested replacement.

The prototype only admits `unqualified_diagnostic` profiles. A claim of qualified independent calibration is rejected by both loader and model construction. Thus a changed flag or small residual cannot upgrade scientific status. General instrument calibration, spatially varying optics, camera nonlinearity and saturated likelihoods remain outside this implementation.

## Geometry and identity

The two-convolution geometry head reads final latent and lifted original image. It returns native boundary logits, bounded signed-distance proxy and log-scale proxy. Its weights cannot overwrite the image. Its own loss can propagate through the image representation, which is verified. All these quantities are untrained; scale is **not** a calibrated uncertainty interval. No confidence is inferred merely from residual magnitude.

Initialization identity, full identity-optics behavior and nonidentity optical corrections are distinct tests. A binary0/1 edge under constrained projection can be a fixed point even with a blur operator. That is why the initial existential nonidentity test was corrected to unsaturated0.2/0.8 intensities; the model was not changed to satisfy an invalid fixture.

## Tiling and resource behavior

Each tile retains only its requested native core and receives context determined from the complete four-step dependency, including the current observation residual used by the prior. Raw pixel origins define the2x lattice, so native odd dimensions and offset tile origins are allowed. Public inference rejects insufficient context or training mode.

With the tested identity profile, required context is64 native pixels; with assumed0.8px Gaussian and2px support it is80; maximum supported16-native-pixel kernel support requires256. This prototype's fixed Raw gradient cue has radius1, below R123's allocated conditioner limit8. Adding broader conditioning, iterations, support or geometry computation requires recomputing and re-testing the bound.

Full default64-channel/four-step nonneutral image output was compared at two core sizes and origins. A separate maximum-support test preserves the same four-step dependency but uses8 channels to isolate the spatial-support question. It does not prove64-channel maximum-support memory capacity. The640 native paired backward check uses64 channels, four steps and block checkpointing under the smaller diagnostic kernel, all FP32 with TF32 disabled; no optimizer step is taken.

## Files and future training boundary

The CLI supports a file or folder of grayscale8-bit inputs, records original hashes, writes floating NPZ and display PNG, and refuses existing output folders. Initialization checkpoints contain configuration, fixed observation buffers and provenance. Reload verifies that buffers match the declared profile; a hidden changed observation gain is rejected. This is not a general trained-model loader.

The R123 small-study data generator, scientific losses, sample ledger and optimizer loop are not yet implemented by this prototype. The backward scalar exists solely to exercise derivatives and memory on representative real inputs, without training on them. Neither unit checks nor untrained SEM diagnostics can substitute for the planned source-independent learning study and actual real-scene benefit.
