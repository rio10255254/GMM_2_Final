# Round 63 — Causal Boundary and Motion Ablation

## Hypothesis

With the optical prior held fixed, static geometry anchoring should improve boundary localization, relative-motion consistency should improve displacement stability, and shift-safe upsampling should reduce translation-sensitive reconstruction artifacts.

## Design

This round is a thesis-focused causal audit of the standalone MOSR model. It does not change the adopted project baseline and it does not ablate the PSF pathway.

The training ablation has three matched parts:

1. A 2 x 2 factorial comparison of static geometry anchoring and relative-motion consistency.
2. Seven single-component removals that separate shape geometry, global boundary position, identity-boundary protection, boundary-region teacher protection, adjacent-frame consistency, known-shift motion supervision, and generic shift equivariance.
3. Three matched retraining removals for the boundary-residual adapter, Raw-position anchor, and quality gate.
4. A matched architecture comparison between shift-safe and ordinary bilinear-plus-convolution upsampling.

An additional inference-only audit removes the boundary adapter, raw-detail anchor, and quality gate one at a time from the same trained checkpoint. This separates training-time causes from output-stage protection.

All comparisons use the same starting checkpoint, fixed data split, two fixed seeds, training budget, validation cadence, and checkpoint-selection rule. The PSF file and all optical settings are identical in every condition.

Because the shared starting checkpoint is already pre-trained, the training contrasts estimate the marginal value of retaining each mechanism during the matched output-stage fine-tuning recipe. They are not presented as full-network training-from-random-initialization ablations.

## Candidates

| Tag | Geometry anchor | Motion consistency | Upsampling | Purpose |
|---|---:|---:|---|---|
| `full_control` | On | On | Shift-safe | Matched control |
| `no_geometry_anchor` | Off | On | Shift-safe | Isolate static boundary supervision |
| `no_motion_consistency` | On | Off | Shift-safe | Isolate relative-motion supervision |
| `no_geometry_no_motion` | Off | Off | Shift-safe | Estimate interaction and unregularized endpoint |
| `no_shape_geometry` | Partial | On | Shift-safe | Remove boundary, centerline, and distance-map reconstruction terms only |
| `no_global_boundary_position` | Partial | On | Shift-safe | Remove the global boundary-position term only |
| `no_identity_boundary_guard` | Partial | On | Shift-safe | Remove low-bias boundary-band protection only |
| `no_region_boundary_teacher` | Partial | On | Shift-safe | Remove the general boundary-region teacher only |
| `no_sequence_consistency` | On | Partial | Shift-safe | Remove adjacent-frame consistency only |
| `no_known_shift_motion` | On | Partial | Shift-safe | Remove known-shift motion-pair supervision only |
| `no_shift_equivariance` | On | Partial | Shift-safe | Remove generic input-output shift equivariance only |
| `no_boundary_residual_adapter` | On | On | Shift-safe | Remove the bounded local boundary-correction head for retraining and evaluation |
| `no_raw_position_anchor` | On | On | Shift-safe | Remove low-frequency Raw-position preservation for retraining and evaluation |
| `no_quality_gate` | On | On | Shift-safe | Remove image-dependent residual scaling for retraining and evaluation |
| `shift_safe_matched` | On | On | Shift-safe | Architecture-matched control with decoder convolutions trainable |
| `standard_upsample_matched` | On | On | Ordinary | Test shift-safe upsampling with the same trainable parameters |

## Primary evidence

- Boundary reconstruction: 10-90% edge width, edge-position error, threshold sensitivity, and nine-pillar CD error.
- Displacement: four real sequences, exactly 30 Raw-ranked steps per sequence, step standard deviation, command MAE, and nine-pillar disagreement.
- Translation fidelity: synthetic subpixel shifts in multiple directions and magnitudes.
- Guardrails: overshoot, ringing, high-frequency excess, and missing-boundary rate.
- Package-manifest-unseen robustness: known synthetic shifts with 720-angle edge and ringing analysis.
- Optional external GMF: appended only if the original source images are restored.

The exact population, metrics, and decision rules are frozen in `PROTOCOL.md` before training results are inspected.

## Status

Complete. All 32 matched training runs, 18,272 candidate reconstructions, locked measurements, paired statistics, claim audit, and figure QA passed the final completeness checks.

The result supports the full MOSR pipeline relative to Raw. At the component level, the Raw-position anchor is supported as a boundary-safety mechanism and shift-safe upsampling is supported for reducing cross-pillar displacement disagreement. Most individual geometry and motion losses do not meet the predeclared causal-claim threshold in this two-seed matched-fine-tuning design.

Read the answer-first report in `reports/R63_RESULTS.md` or the portable self-contained report in `reports/R63_RESULTS.html`. Thesis text remains untouched pending discussion.

## Data

- Standalone model package: `Thesis_MOSR_Evidence/LabSystem_MOSR/Model_Packages/V42_SoftLabelSNR_FullStandalone_20260709/`
- Training outputs: `results/training_runs/`
- Evaluation outputs: `results/evaluation/`
- Key finding table: `results/evaluation/aggregate/R63_key_findings.csv`
- English MATLAB figures: `figures/`

## Branch

The shared workspace currently contains unrelated uncommitted work on `sandbox/r45`. To preserve it, this round is isolated by directory and artifact identity; no branch switch is performed in the shared worktree.
