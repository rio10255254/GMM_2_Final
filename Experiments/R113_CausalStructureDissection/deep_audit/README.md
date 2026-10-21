# R113 Deep Model and Training-Image Audit

This phase extends the completed R113 causal dissection.  It is read-only with
respect to every source checkpoint, training array, and earlier result.

## Questions

1. Do the 5,000 training and 512 validation scenes cover the intended geometry,
   polarity, texture, transition width, and difficult degradation space without
   hidden duplicates or split leakage?
2. Which source-target pairs contain recoverable boundary/detail information,
   and which are intrinsically ambiguous after degradation?
3. Which internal R109 layers encode geometry versus appearance, and where do
   the boundary, width, shift, support, and proposed detail paths saturate?
4. Which losses actually update each module, and which losses reinforce or
   oppose one another on easy, hard, identity, and flat-negative scenes?
5. Can the current failures be assigned to data, information loss, supervision,
   control parameterization, or renderer capacity with saved evidence?

## Completion contract

- Profile all 5,512 records and every target/mask/SDF file.
- Check exact and perceptual duplicates within and across splits.
- Measure label geometry, edge antialiasing, SDF agreement, topology, texture,
  polarity, midpoint, and target-width distributions.
- Recreate deterministic degradations and quantify visibility/recoverability by
  family and challenge.
- Audit effective receptive field, activation statistics, representation
  invariance, head saturation, and checkpoint evolution.
- Measure per-loss gradients and pairwise gradient conflicts for every major
  parameter group on stratified scenes.
- Execute a companion notebook and independently validate headline numbers.
- Do not start another training run from this audit.

