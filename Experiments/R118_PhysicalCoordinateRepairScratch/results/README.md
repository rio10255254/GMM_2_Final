# R118 result directory guide

These are distinct historical or preparation outputs, not interchangeable runs.

| Item | Role |
|---|---|
| final_probe_acm | Complete R73/R74 development ACM for the verified R118 E12 |
| final_probe_sem | Complete Raw/R118 E12, 36-pillar SEM development comparison |
| repair_probe_acm | Earlier repair diagnostic, not the final reference |
| repair_probe_sem | Earlier repair diagnostic, not the final reference |
| inference_entry_smoke | Inference packaging test, not capability validation |
| probe_comparison.json | Matched controls; pooled pair dispersion is not real repeatability |
| handoff_preparation | Input audits/checker tests for the next-work handoff, no training |

Training attempt roles are in ../runs/RUN_INDEX.json. The prepared next work was
executed in ../R119_SequenceGeometryValidation; its interpretation is in that
folder's reports/R119_RESULTS.md and reports/CLOSEOUT.md. These completed R118
outputs remain historical references and are not overwritten.
