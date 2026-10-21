# R109/R119 matched readout and path comparison

Canonical report: ../../reports/R119_R109_READOUT_COMPARISON.md

Frozen R109 E48 and R119 E42, all 36 pillars and 12 exposures; nine diagnostic outputs, two SEM references. No training, confirmation use or model promotion.

Actual routes are in render_v2.py and protocol_v2.json. Initial render.py used the generic R109 core1024 default; historical suite records proved core512. Its failed first attempt is preserved. V2 reproduces both models byte-for-byte at all exposures without changing expected outputs.

measure_acm.m retains the historical helpers and reports both legacy and common Raw-derived alignment. profiles.py calibrates midpoint and steepest-point readouts and preserves invalid profiles. operator_sanity.py checks the position/width coupling on clean known-target examples. analyze.py separates reliable three-way comparisons, inadequate slope coverage and explicitly secondary model-only comparisons. verify.py independently checks numerical results and all 132 protected inputs.

Raw/R109 rankings depend on readout; primary slope coverage is insufficient. R119 position removal helps, but this path also sharpens and cannot be described as pure translation. R109 is not physical ground truth. Old audits and R121 negative results are not revoked.
