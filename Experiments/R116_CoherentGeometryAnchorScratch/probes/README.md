`r109_counterfactuals.py` produces four image folders from the frozen R109 E48
checkpoint without training:

- current R109 output;
- R109 with normal shift disabled;
- Raw plus one-half of the locally high-passed R109 residual;
- the R109 geometry-warped Raw anchor plus one-half of its locally high-passed
  detail residual.

These folders are for the same locked external GMF flow.  Internal template
scores must not be used to promote one of them as an external-GMF winner.
