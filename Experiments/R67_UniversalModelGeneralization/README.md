# R67 Universal Model Generalization

## Question

Which frozen project model is the safest single choice across the available magnifications, motion sizes, and feature morphologies?

## Decision rule

The primary ranking is worst-case-first. A model must have complete outputs and no hard measurement failures, then the model with the smallest worst observed normalized regret ranks first. Excess error is scaled by the typical candidate result in each measurement cell so zero-error cells stay finite. Median performance is only a tie-breaker.

## Scope

Phase A re-runs all frozen candidates on the four existing 20x/50x motion sequences and evaluates pillar, via, and line measurements with the existing locked protocols. These sequences were used during model development, so Phase A can select a current-data leader but cannot certify universal generalization.

Phase B is reserved for sealed, unseen samples and independent position/reference truth. No model may receive the `universal_pass` label until Phase B is populated and passes.

## One-command use

```powershell
& 'C:\Users\Rio\anaconda3\python.exe' scripts\run_r67.py --stage all
```

The command is resumable. Completed reconstructions are checked and reused.
