# Active R130-Clean task

User explicitly requested reading and executing C:/Users/Rio/Downloads/R130_Clean_Codex_建構訓練完整規格.md. This supersedes earlier paper-preparation work for this task. The full objective includes scratch8192 training, generated dev/test,930native reconstructions, unchanged ACM/PI/SEM comparisons for Raw/R129/R130-Clean, profiling and final reports. Do not stop at training launch or claim completion from a step counter.

Execution root: D:/GMM_2_Final/Experiments/R130_Clean
Current exec session:3846. Pipeline/training process originally20344. Consult runs/formal_8192/status.json and runs/pipeline_status.json for current phase. Do not restart an incomplete formal run; the pipeline is already live and automatically advances.

Preflight completed:300101params; no pretrained/optimizer/EMA; noPSF; exact initial identity; 32-step sanity separate and discarded; nonneutral full/tile difference0; full384versus320crop core difference0, gradient relative1.51e-7. Native dependency radius82, halo96; all synthetic shifts <.9px, required context84. Residual cap.35, eta initial.05, max.25, one tanh. All frozen before formal start.

Code/data/config lock:config/source_lock.json. Checkpoints verify it every128updates. Never modify frozen code while training. Reports, runtime status and independent audits are not frozen code. Protected historical files are in config/protected_sources.json and remain unchanged. No old checkpoint is loaded even for the R129 baseline; its cached outputs and history are used.

Data:768 unchanged existing synthetic parents; local data extracts onlysource/noiseless/target, with minimal metadata, no synthetic kernel/latent/SDF payload. All arrays and split/source checks passed. Actual input hashes independently reproduced at3early steps. Own checkpoint4224 independently inspected:all21parameter tensors updated; optimizer steps agree. These audits are inresults.

Bulk reconstruction output is a junction from results/reconstruction to H:/GMM_2_Final_Archive/active_runs/R130_Clean_20260920/reconstruction. D had~14GBfree atlaunch; H~2.7TB. Storage registered. Old R130_CleanV42Comparison and R129 untouched. Reserved branch codex/r130-clean created atHEAD; existing dirty checkout was not switched or reset. Source hashes carry new uncommitted source identity.

Automatic pipeline:train_r130_clean.py -> evaluate_real_measurement.py -> compare_measurements.py -> profile_r130_clean.py -> write_report.py. It uses the frozen corrected corner9 Raw tracking and exact existing reader function bodies/core; both old SEM orientation candidates retained. All real model evaluation is gated on completed8192final checkpoint. Output readers and baselines must reproduce; failures are recorded, not overwritten with passing hashes.

After pipeline completion:inspect all report plots and actual results; independently reconcile final8192update/optimizer/input/protection facts and930outputs; report advantages and shortcomings candidly. R130 full/tile is freshly profiled. Cached R129 end-to-end timings include IO and are explicitly not a fresh neural-only benchmark. Profiling allocated GPU memory is process-local; reserved allocator cache may persist across measured modes.

Project_state and Experiments/INDEX currently marklaunch/preflight, notcomplete. Update these and appropriate research notes in ESTIMATOR_POLICY atactualcloseout without changing COMBO formal baseline. Do not alter historical evidence artifacts or use theold144confirmation set. Figures/report results are not grounds for auto baseline adoption.
