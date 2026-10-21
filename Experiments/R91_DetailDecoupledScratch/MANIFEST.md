# R91 Manifest

## Identity

- Experiment: `R91_DetailDecoupledScratch`
- Training: one random-initialization run, seed 910041
- Dataset: 1,250 procedural latent scenes and 5,000 observations
- Training labels: drawn at 8x and reduced once with area antialiasing
- Maximum epoch: 60
- Formal baseline changed: no

## Isolation

- No checkpoint inheritance or resume
- No teacher or pseudo-label model
- No SEM or HS100MG pixel, contour, position, or structure in training
- Only anonymous aggregate noise, illumination, row/column pattern, and radial-spectrum statistics are retained

## Native changes from R90

- Broad illumination correction is produced at quarter resolution.
- Fine and medium texture corrections are learned separately and remain locally zero-mean.
- Each coherent exposure scene is trained as a four-view bundle.
- Persistent target texture and independent nuisance noise are explicitly separated.
- Model selection uses a continuously updated six-axis Pareto archive.

## Expected artifacts

- `data/r91_formal/manifest.json` and `audit.json`
- `data/r91_locked_holdout/SEALED.json`
- `config/implementation_lock.json`
- `results/preformal_benchmark.json`
- `runs/launcher_logs/active_formal_run.json`
- `runs/training_*/training_log.csv`
- `runs/training_*/pareto_archive.json`
- `weights/formal/seed_910041/*/weights/epoch_*.pth.tar`
