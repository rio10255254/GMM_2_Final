# R108A Existing-Model Oracle and Predictability

## External truth-backed shapes

- Common images: 200 across 10 held-out families.
- Global best method: R61 with median boundary distance 0.5911 px.
- Per-image oracle median: 0.4323 px.
- Oracle improves over the global best on 64.5% of images; median gain 0.1097 px.

## Can Raw alone predict the useful model?

- Leave-one-family-out Raw-feature selector top-1 accuracy: 47.0%.
- On the decisive half of cases: 61.0%.
- Median selected boundary distance: 0.5427 px; median regret to oracle: 0.0082 px.
- Generator-metadata selector top-1 accuracy: 51.5% (diagnostic upper context, not deployable input).

## SEM repeated observations

- Common observations: 432 from 36 physical pillars and 12 exposures.
- Global best method: R79E23.
- Global-best median boundary distance: 0.2468% pitch.
- Per-observation oracle median: 0.2467% pitch.
- Per-pillar fixed-choice median: 0.2405% pitch versus 0.2405% for the global best.

## Interpretation rule

Large oracle gain plus successful Raw-only prediction supports conditional local action selection. Large oracle gain without Raw-only predictability indicates a single-image information limit. Small oracle gain indicates that recombining existing behavior is not enough and a new optical action is required.
