# R123 — Real-first next-model design

Self-contained design and read-only benchmark study, 2026-09-08. Branch `codex/r123-real-first-design`.

The user places real microscopy and SEM comparisons first. This round selects a next architecture, designs independent training data, inventories actual real evaluation sources and exercises the decision contract on existing real results. It does not train a model or certify new performance.

Recommended direction: full 2D iterative reconstruction with a qualified, fixed image-formation model and an auditable geometry representation. The old position/width/detail action heads are not mandatory. R122's continuous-profile tests remain diagnostic tools, not the only possible renderer or the primary success benchmark.

- `reports/R123_DESIGN.md`: concrete architecture, evidence and alternatives.
- `reports/R123_DATA_AND_VALIDATION.md`: data roles and real-first acceptance.
- `reports/R123_RESULTS.md`: what was actually verified in this design round.
- `config`: proposed engineering settings and source/validation contracts.
- `scripts`: read-only intake, historical real-result replay and design checks.
- `results`: generated inventories, paired summaries and checks; no model predictions are fabricated.

Budget 0.25 GiB. Raw data and all old evidence remain in place; the entire small new folder is retained locally. No confirmation image payloads are accessed. Completion means a reviewed, concrete design with verified inputs and explicit unresolved calibration requirements, not a useful model already exists.
