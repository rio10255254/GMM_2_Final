# R113 Causal Structure Dissection

This experiment isolates why V42 E120, R61 v16, and R109 E48 behave differently.
It does not overwrite any source checkpoint or prior result.

## Decision question

Determine whether R109 is limited by its renderer, its learned controls, its
training trajectory, or the measurements used to judge it.  External GMF is a
compatibility readout only; synthetic truth, SEM contour truth, deterministic
LSC, real-image safety, and tile parity control the scientific decision.

## Completion contract

1. Freeze and hash every checkpoint and source dataset used.
2. Repair the R112 annulus and radial-profile measurements in a new result tree.
3. Measure the best result that the current R109 renderer can express when its
   width and shift controls are optimized directly against known truth.
4. Run causal component interventions for V42, R61, and R109 on matched inputs.
5. Trace representative checkpoints to separate architecture from training time.
6. Validate promoted mechanisms on synthetic truth, SEM ACM, deterministic LSC,
   real 5x/20x/50x appearance, and multiple tile grids.
7. Authorize a small scratch comparison only when a mechanism is supported on
   more than one physical validation family.
8. Recompute headline values independently and write a machine-readable final
   validation record.

## Safety

- Source checkpoints and earlier experiments are read-only.
- New outputs live only under this directory.
- No real SEM or JunHua image is used as a training label.
- No result is called causal unless it comes from an explicit intervention.
- GMF-only improvement cannot promote a scientific reconstruction change.

