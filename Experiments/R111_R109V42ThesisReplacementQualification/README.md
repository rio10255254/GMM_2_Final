# R111 R109 versus V42 thesis-replacement qualification

This experiment is complete. It does not retrain either model. It freezes V42
epoch 120 and R109 epoch 48, preserves the thesis Raw-selected populations and
measurement rules, and fills the evidence cells required before deciding
whether R109 may replace V42 in the thesis.

The tests cover the frozen 120 displacement steps, static center-nine CD,
threshold-robust CD, 20x/50x edge behavior, line-pattern transfer, shared SEM
contours, tile parity, and the same-frame external GMF comparison.

No result from R109 is allowed to change the Raw selection list, SEM mapping,
feature centers, thresholds, or validity rules.

The final policy treats SEM ACM, least-squares-circle (LSC) center displacement,
and external GMF stability as the primary outcomes. CD is secondary
dimensional-compatibility evidence and does not control the decision. The
current Chapter 6.2 top-30 LSC rerun finds V42 and R109 statistically
equivalent. V42 remains the thesis-results model because its external-GMF
stability is decisively stronger; R109 is retained as the stronger
generalization, dark-exposure, line-pattern, and engineering research extension.

The LSC audit resets the stateful alternating Chan-Vese curvature operator
before every pillar and method measurement. Without this reset, repeated calls
on the same patch alternate between two answers and method order can bias the
comparison. The corrected run has zero repeat difference in its spot check.
