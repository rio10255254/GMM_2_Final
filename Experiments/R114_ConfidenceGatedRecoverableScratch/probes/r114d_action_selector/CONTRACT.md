# R114D causal action-selector probe contract

This is an isolated research probe.  It does not modify or replace the main
R114 model or training program.

## Frozen proposal

- The only proposal generator is the sealed R114C epoch-24 checkpoint.
- Its file hash, required epoch, architecture, geometry, and bounded analytic
  profile parameters are pinned by `config.json` and loaded strictly.
- Every proposal parameter has `requires_grad=False`, stays in evaluation mode,
  and is excluded from the optimizer.

## Permitted learned decision

The selector receives only local inference-time values derived from the input
image and frozen proposal.  It predicts:

1. `acceptance`: whether the frozen proposal is causally useful here;
2. `amount`: the fraction of that frozen proposal to apply.

Both maps and the selected action are exactly zero at initialization.  The
deployed causal gate is exactly:

`boundary * need * recoverability * acceptance * amount`

The frozen E24 10-to-14-pixel profile band is applied after this causal gate.
The action direction remains E24's learned `profile_proposal_delta`, including
its 48-gray hard bound.  There is no free residual.

## Online labels

Each training step measures the frozen learned proposal against the geometry
base and target.  The acceptance label comes from signed error reduction.  The
amount label is the clipped least-squares alpha along that same frozen proposal
direction.  The label builder does not derive oracle midpoint, contrast,
width, visibility, shift, or any replacement profile.

Supervision is restricted to the true boundary band and three hard-negative
types: harmful proposal direction, already-clear base, and identity examples.
Identity pixels outside the true band are admitted only when the frozen action
would be nontrivial, are ranked by action risk, and are capped at the number of
true-band pixels in that scene.  They therefore remain a controlled hard-
negative set rather than a full-image background loss.
Positive and negative reductions are class-balanced, so the full-image
background cannot dominate.  Negative acceptance is weighted three times more
than positive acceptance and an additional false-positive product penalty is
applied.

## Advancement rule

CPU/GPU smoke tests and all contract tests must pass before a short probe is
launched.  A short probe is never started by importing this package and must be
explicitly launched with `python -m probes.r114d_action_selector.trainer`.
