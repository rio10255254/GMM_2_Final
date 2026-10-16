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
- Recovery2026-09-09: original process interrupted after1393updates by progress-file replacement denial. Original checkpoint1280, all previous scientific source identities and evidence are retained. recovery/20260909_progress_io_v1 adds separately tested mutable-progress I/O retries and execution supervision; no model/data/loss/optimizer/evaluation changes or rebaselining. Replayed steps are kept separately and not counted twice.
- Independent launch2026-09-09 17:12: first2runs verified complete; third run stopped after5359updates when both processes disappeared near an application-update/NVIDIA event. Unique cause unproven. A separately recorded one-off Windows-service-parented launch resumes checkpoint5248 using the same unchanged coordinator/trainer. Windows job independence and exact four-update replay verified; see recovery/20260909_external_stop/launch_manifest.json. No recurring task or scientific-protocol revision.
