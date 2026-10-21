# R113 frozen-model structure findings

All structural checks passed across 8 matched cases and 184 saved outputs.

## Architecture relation

- R61 and V42 use byte-identical model source code.
- 112 of 135 shared tensors are byte-identical.
- All learned groups through `u1` are unchanged. V42 changes `p1`, `out`, and the boundary adapter, then adds a four-tensor quality gate and a parameter-free Raw-detail anchor.
- R109 is a separate, much smaller renderer (678,291 parameters versus roughly 4,024,238).

## Causal results

- V42 Raw anchor removal changes the final image by a median 38.98 gray levels. This is the dominant final constraint.
- V42 weak PSF removal changes exactly 0 gray levels because its learned beta scale is zero.
- R61 checkpoint-native PSF behavior and the locked PSF-off deployment are separate. Their median difference is 5.19 gray levels.
- R109 learned support is nearly constant: mean 0.432045 to 0.432056, maximum spatial std 0.000267.
- R109 has no learned necessity gate (`necessity=1`). Width is the principal enhancement branch; normal shift is secondary and scene-dependent.
- Smoothed R109 controls remain close to full output (median 0.230 gray), so this is a justified SEM-ACM probe, not yet a promoted model change.

## Boundary

No architecture change is authorized from appearance metrics. Exact SEM ACM and deterministic LSC on the exported intervention stack must decide the next change.
