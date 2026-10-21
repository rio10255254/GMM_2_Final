# R112 model-side GMF mechanism conclusion

## Outcome

There is a credible model-side path to improve R109. The evidence points to
output parameterization, not a need to copy the full V42 model.

## Strongest evidence

- Deterministic LSC: V42 and R109 are equivalent.
- External GMF Y-step SD: V42 1.660 px; R109 4.538 px.
- Median low-frequency residual share: V42 3.9%; R109 60.6%.
- V42 without its Raw anchor changes the crop by 24.1 gray levels instead of 1.3; the anchor is the dominant final-output constraint.
- R109 upper-tail normal-shift changes correlate with external step error (Spearman 0.287, p=0.0040).

## Recommended model change

Keep R109's geometric detector. Predict smoother low-resolution width and shift
fields, warp Raw to create a geometry anchor, and add only a bounded local
high-frequency residual whose local mean remains tied to that anchor. Train
normal-profile consistency across synthetic exposure/noise/blur pairs.

## What not to do

- Do not simply append the V42 Raw-anchor formula to the current R109 output;
  the current predictor carries too much high-frequency energy and the simple
  wrapper trades template consistency against ring-width stability.
- Do not enlarge the full backbone first.
- Do not trust the internal fixed-template surrogate; it failed to reproduce
  the observed external-GMF ranking.

## Before training

Externally test only two cheap counterfactuals: R109 without normal shift, and
Raw plus 0.5 times the high-frequency R109 residual. Promote the architecture
only if one improves GMF without weakening ACM, deterministic LSC, line, or
tile-parity behavior.
