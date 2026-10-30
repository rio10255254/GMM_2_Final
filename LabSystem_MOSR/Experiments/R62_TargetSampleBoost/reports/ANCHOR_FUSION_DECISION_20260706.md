# Anchor Fusion Decision 20260706

Purpose: test a fixed reconstruction output rule that keeps Raw image position stable while adding only a small amount of model reconstruction detail. This is not per-sample calibration: the same blend ratio is applied to every frame in each sequence.

## Candidate

- Current safest candidate: `anchor_blend10`, meaning 90% Raw + 10% V7 reconstruction.
- Rejected as unsafe: `anchor_blend40` for 100MG GMF, because it damages the 1um local-pillar center tracking.
- Rejected for long training as-is: V14/V15/V16 low-frequency guard probes, because seeded GMF did not recover 100MG 1um stability.

## Edge-Phase Open Algorithm, Raw vs Blend10

| dataset/group | Raw median step um | Blend10 median step um | Raw std um | Blend10 std um | Raw error um | Blend10 error um |
|---|---:|---:|---:|---:|---:|---:|
| x_1um | 0.0297 | 1.0050 | 0.4342 | 0.0112 | 0.9703 | 0.0050 |
| x_0p5um | 0.0518 | 0.4999 | 0.4058 | 0.0508 | 0.4482 | 0.0001 |
| 20x_1um | 1.0053 | 0.9984 | 0.0242 | 0.0247 | 0.0053 | 0.0016 |
| 20x_0p5um | 0.4987 | 0.4944 | 0.0780 | 0.0761 | 0.0013 | 0.0056 |
| 5x_1um | 0.9073 | 0.9173 | 0.1550 | 0.1566 | 0.0927 | 0.0827 |
| 5x_0p5um | 0.5111 | 0.5092 | 0.0162 | 0.0157 | 0.0111 | 0.0092 |

## GMF Cross-Check, Raw vs Blend10

| group | signal | Raw std um | Blend10 std um | Raw step error um | Blend10 step error um | readout |
|---|---|---:|---:|---:|---:|---|
| x_1um | intensity | 0.0301 | 0.0311 | 0.0023 | 0.0065 | usable local-center check |
| x_0p5um | intensity | 0.0571 | 0.0563 | 0.0176 | 0.0175 | usable local-center check |
| 20x_1um | intensity | 0.0350 | 0.0363 | 0.0034 | 0.0041 | usable local-center check |
| 20x_0p5um | intensity | 0.0805 | 0.0808 | 0.0089 | 0.0089 | usable local-center check |
| 5x_1um | intensity | 0.3228 | 0.3169 | 0.2041 | 0.2104 | usable local-center check |
| 5x_0p5um | intensity | 0.0473 | 0.0509 | 0.0518 | 0.0516 | usable local-center check |

## Decision

The only candidate worth promoting right now is the fixed `anchor_blend10` output mode. It gives large gains on the 100MG edge-phase readout and small-to-moderate gains on parts of the 20x/5x edge-phase readout, while remaining close to Raw under GMF local-center checks. It is not yet a universal displacement win, so it should be treated as a candidate reconstruction mode, not a completed thesis claim.

Next technical move: integrate `anchor_blend10` as a standard post-inference reconstruction mode and use it in the thesis analysis package, while avoiding long training of V14/V15/V16 unless a new architecture makes the output natively position-anchored.

## Evidence Files

- Open phase sweep: `anchor_blend_alpha_sweep_phase_20260706/alpha_sweep_phase_summary.csv`
- Fast phase comparison with saved images: `anchor_fusion_fast_phase_eval_20260706/fast_phase_summary.csv`
- GMF cross-check: `anchor_blend40_gmf_eval_20260706/blend40_gmf_summary.csv`
- Fusion tool: `Tools/Displacement_Algorithms/scripts/motion_preserving_fusion.py`
