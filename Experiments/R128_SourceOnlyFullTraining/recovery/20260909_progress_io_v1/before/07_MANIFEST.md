# R128 run identity

- Profile: self-contained.
- Run family: R128_SourceOnlyFullTraining.
- Candidate identifiers: I_s1285001, P_s1285001, I_s1285002, P_s1285002.
- I: image/latent/gradient/physical-pair reference objectives.
- P: exactly the same, plus independently specified true observation consistency after model forward.
- Every run:8192optimizer updates, shared deterministic scene/noise order; fixed final step is the primary comparison.
- New-data roles:512train,128dev,128final generated test. Old real/SEM/teacher data are not training inputs or labels.
- Native data field384, center128; required context is proved for the new source-only architecture before use.
- Capacity24GiB; checkpoints/logs/data retained; no archive/deletion.
- Completion claims require actual run/checkpoint/log/output reconciliation. Starting a full run is distinct from finishing it or demonstrating real usefulness.
- Launch verified2026-09-09: results/launch_verification.json reconciles the first256-update checkpoint, actual optimizer state and sampled consumed input bytes. Remaining execution is visible in reports/TRAINING_PROGRESS.md; no completed-study or model-adoption claim.
