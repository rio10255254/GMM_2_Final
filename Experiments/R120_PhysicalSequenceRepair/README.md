# R120 Physical Sequence Repair

Start with MANIFEST.md and reports/R120_RESULTS.md.
This package implements and tests the corrections identified in the R119 causal
audit. Old R119 metrics and receipts are retained as historical evidence.

The intended comparison uses the unchanged R118 model/objective and independently
initialized A/B arms. A must match R118's dataset behavior byte for byte. B changes
only the declared observation schedule on a fixed training subset. All evaluation
inputs/targets are shared. New observations are generated at 8x before integration.

Use C:/Users/Rio/anaconda3/python.exe. Commands and results are documented only
after they have run. Historical real/SEM data and consumed confirmation are never
training sources. The package currently has no selected or promoted model.
