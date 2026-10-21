# R114E decoupled hybrid causal probe contract

This directory is an isolated research probe. It does not edit or replace the
main R114 architecture, trainer, data, or any R114C checkpoint.

## Frozen sources

- R114C E20 is the only source of controller maps, width action, normal shift,
  shifted base, and final geometry base. Its path, SHA-256, epoch, and stage are
  pinned in `config.json`.
- R114C E24 is used only by directly evaluating its renderer backbone and its
  four profile heads: midpoint offset, signed contrast, profile width, and
  profile visibility. E24 controller, width head, shift head, geometry action,
  base, and `forward_details` are forbidden in the hybrid path.
- Both source models are frozen, remain in evaluation mode, and are excluded
  from every optimizer.

## Decoupled action

The E24 profile parameters are re-rendered on E20's base, shifted base,
controller, and predicted signed distance. The bounded analytic profile action
and 48-gray limit remain unchanged. The learned selector can only predict two
local maps: `acceptance` and `amount`.

The full causal safety gate is exactly:

`E20 boundary * E20 need * E20 recoverability * acceptance * amount`

The E20-derived 10-to-14-pixel profile band is then applied. At selector-zero,
the selected delta is exactly zero and the output must be bit-identical to E20.

## Advance rule

Before any selector training, the fixed first 128 validation records must prove
that the decoupled learned direction has material oracle headroom. Thresholds
are frozen in `config.json`. If any threshold fails, the probe stops and no
training is authorized. Passing the gate only authorizes a separate short
selector probe; it does not authorize a long or formal run.

