# R61 STEP Generalization 20260623

This folder collects the recent R61 multi-round tests that were previously at the project root.

## Role

R61 has two roles:

1. It belongs to the main R-series experiment line, because it is a multi-round model-design and validation effort.
2. It also supports the thesis/lab evidence line, because the current Step validation and v16 reconstruction evidence may use this model family as a main thesis candidate.

This means R61 is not scratch output. It should be read as a candidate model family with thesis relevance.

## Current Interpretation

- Formal production baseline is still COMBO / r38v2_8px_gate_p95.
- R61 is not promoted as a formal baseline.
- The most thesis-relevant run here is `R61_stepguard_v16_dpv96_matched_20260623`.
- The current evidence supports Step-sample boundary/CD preservation and displacement stability, but it does not prove universal cross-sample guarantee.

## Folder Map

- `runs/`: full R61 run folders moved from the project root.
- `R61_RUN_INDEX.csv`: compact run index with paths, roles, case counts, and key summary values.
- `R61_MOVE_MANIFEST.csv`: old root paths and new locations.
- `R61_FILE_INVENTORY.csv`: full inventory after the move.

## Key Runs

| Run | Role |
|---|---|
| `R61_m11_dpv96_20260623` | early motion-v11 ablation |
| `R61_motiongrad_dpv96_20260623` | motion-gradient ablation |
| `R61_motiongradv11base_dpv96_20260623` | motion-gradient with v11 base comparison |
| `R61_motiontexture_dpv96_20260623` | motion-texture candidate before Step guard |
| `R61_stepguard_v16_dpv96_20260623` | v16 Step-guard candidate, smaller phantom validation |
| `R61_stepguard_v16_dpv96_matched_20260623` | current thesis/main-model candidate phantom validation |

## Links To Lab/Thesis Evidence

- Step working analysis: `Step_analysis_20260623`
- Step curated evidence: `Step_analysis_20260623/_curated_final_20260624`
- Thesis evidence entry: `Thesis_MOSR_Evidence/Experiments/20260624_STEP_boundary_displacement_cd_validation`
- Central archive: `_MOSR_Project_Archive_20260624`

## Guardrails

- Do not mix R61 thesis evidence with 100MG SEM/CD evidence unless a matching scale and sample reference is used.
- Do not describe R61 as a formal replacement for COMBO until external GMF and thesis-specific validation are both explicitly satisfied.
- Keep the Step certificate evidence tied to the Step sample.
