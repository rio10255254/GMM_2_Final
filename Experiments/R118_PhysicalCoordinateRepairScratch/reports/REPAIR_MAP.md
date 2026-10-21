# Repair map

| Diagnosed issue | Implemented repair | Evidence |
|---|---|---|
| Preview inputs were R109 outputs | Verified pre-R109 Raw paths and SHA-256 checks at each preview | preflight.json; per-epoch sources.json |
| Intensity normal disagreed with distance sign | Normals come from the same signed distance field used for sampling | test_geometric_direction_independent_of_brightness; sign-reversal covariance test |
| Width had a neutral discontinuity | Subtract the neutral mapping continuously; integrate the correction on a 2x grid | neutral continuity and monotone straight-edge tests |
| Protection projection created rings | Remove reflection projection and repeated high-pass enforcement | source inspection; actual Raw previews; ACM/SEM probes |
| Geometry pair term could not update geometry | Geometry remains active through all stages | autograd test and preflight gradient measurement |
| Radial average missed x/y translation | A 2x2 reference-gradient location fit; undefined flat locations excluded | known 1px and half-pixel tests; flat test |
| Different blur was forced to use equal correction | Compare restored-reference errors, not width/shift action maps | perfect-reference pair penalty is zero |
| Target width gain exceeded actuator ceiling | Remove prescribed Gaussian/logistic gain targets | no gain-target loss remains |
| Dense edge counts dominated learning | Per-scene normalization plus one-pass family interleaving | weight invariance and sampler tests |
| Clear views were appended to all scenes | Two observations; only dedicated identity scenes request identity | dataset behavior test |
| Blurring happened after downsampling | 8x latent blur before sensor integration | exact 5,512-reference replay; physical observation records |
| Fine labels could demand erased frequencies | Synthetic visibility/noise weighting of true error; retain flat denoising | erased-texture and actual-loss attenuation tests |
| Proxy energy was reported as detail fidelity | Compare gradients directly to known reference; keep ACM separate | development validation tables and locked ACM results |
| Reused test sets were called sealed | Mark legacy suites as development; generate separate unopened confirmation set | confirmation/manifest.json |
| Smoke checks proved execution, not learning | Multi-stage scratch probes, matched branch comparison, real Raw previews, full R74 and shared SEM checks | runs and results |
| Program/data organization and manual run | All runtime code and data under R118; IDE entry points and compact ETA monitor | Train.py check-only; inference smoke; PowerShell parser |

## Remaining empirical limits

The repair addresses implementation and training-contract errors. It does not
prove universal recovery. Optical PSFs are explicit synthetic priors, not
independently identified microscope kernels. The available 5x noise estimate
is potentially biased by periodic structure. Corners and closely spaced
boundaries still require validation of the learned distance field. Native
tiling is tested with non-neutral model outputs; real displacement stability
and final model selection must not be inferred from a finite loss alone.

Training probes with and without detail use the same seed, dataset and update
budget, but GPU kernels are not guaranteed bit-identical. The short probes'
legacy asymmetric-halo regression and their remaining paired-position
variance are retained as negative results, not hidden by aggregate gains.
