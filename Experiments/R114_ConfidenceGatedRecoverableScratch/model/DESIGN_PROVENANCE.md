# R114 controller model provenance

This folder implements only the Controller Viability Probe.  It does not
authorize or start formal R114 training.

## Safely reused ideas

- R109's grayscale, local multi-scale cues: fixed Gaussian views, high-pass
  views, finite differences, local scale and locally normalized contrast.
- The 48-channel model scale and the local dilation schedule
  `1,2,4,8,8,4,2,1`.
- A fully local forward path so large images can be reconstructed from
  overlapping tiles.
- Scratch construction and explicit detailed outputs for diagnosis.

No R109/R113 parameter tensor or checkpoint is loaded or copied.

## Explicitly removed

- Detector/renderer terminal `tanh` feature saturation.
- Zero-initialized output heads that begin with zero input sensitivity.
- Constant `necessity = 1`.
- `max(raw_gradient_support, learned_floor)` and every other forced raw-gradient
  support floor.
- Patch-wide GroupNorm, pooling, FFT and global quality gates.
- R113's bounded-detail branch; detail is outside Controller Probe scope.
- Renderer width/shift and any free image residual; those belong to later
  probes only after this controller demonstrates viability.

## Output contract

The controller returns six named items at input resolution:

1. `normalized_sdf` (one linear channel; no terminal `tanh`),
2. `normal_x`,
3. `normal_y`,
4. `boundary_confidence`,
5. `correction_need`,
6. `recoverability_uncertainty` (two softmax channels: recoverable,
   uncertain).

The convenience gates are derived, never forced from the raw gradient:

- geometry gate = boundary confidence x correction need;
- detail gate = geometry gate x recoverability.

The exact local dependency radius is 101 pixels.  The shared model config keeps
the more conservative 192-pixel production halo, and `forward_tiled` rejects a
smaller value.  The model loads its default 48-channel architecture contract
from `config/model.json` while still permitting explicit compact probe configs.
