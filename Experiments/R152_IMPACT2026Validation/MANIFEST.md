# R152 IMPACT2026 manifest

- Role: validation-only follow-up; no model training or promotion.
- Profile: shared-mainline read-only references to D:/GMM_2_Final; independent branch sandbox/r152-impact2026.
- Main scope: 166 native frames, 120 original locked pairs, Raw/Fixed Wiener/R152, 4482 centers and 360 pair measurements.
- R152 identity: delivered checkpoint 17bf7c63f070520a5ef8d4428010340686f465bf1fa03ef8225c0a2eadad4a61, multiplier 1, learned parameters unchanged.
- Optical inputs: original native 25-kernel 20x bank; original single calibrated 50x PSF through the authorized inference-only adapter.
- Main outputs: results/full120; results/20x; results/50x_calibrated.
- Supplement: results/shared_bank120 and results/50x_shared_bank. Retained irrespective of comparative scores.
- Current reports: reports/R152_RESULTS.md and reports/R152_AUDIT.md. Earlier stage: reports/history_20x_stage.
- Latest poster entry: poster_final/START_HERE.md; public model name MOSR, original four conditions, sample SD of 30 single steps per condition. Mean SD reduction 19.5%. Separate 30-scan data excluded.
- Poster verification: poster_build/mosr_step_sd_final_verification.json and poster_build/mosr_native_editability.json.
- Latest numerical sources: results/localization_improvement; original manuscript-reader replay retained in results/full120.
- Provenance: results/source_manifest.json; config/objective_optics_authorization.json; results/objective_adapter_preflight.json; per-image reconstruction receipts.
- Verification: results/full120/delivery_verification.json.
- Retention: preserve the whole audit and inference package plus all referenced D paths. No source model, image, prior result, or formal baseline modified.

- Current poster: poster_final/START_HERE.md; 20x thesis run 7 (first evaluation scan) and original 50x 1um locked pairs, 30 steps each. No pooling.
- Full supplemental validation: 930 thesis frames remeasured for all three methods, plus 86 fresh 50x reconstructions; results/separate_conditions.
- Current poster source: results/separate_conditions/poster_data_30steps.json; verification: poster_build/thirty_final_verification.json.

- 2026-10-03 current poster: poster_final/IMPACT2026_MOSR_Design_TW0243_v3.pptx and matching PDF/PNG.
- Design-only update: functional native diagram, actual 64-point boundary/center evidence, same two 30-step datasets, public notes scrubbed of private dossier details.
- Verification: poster_build/design_final_verification.json and design_editability.json.

- 2026-10-28 imported into main from the independent worktree C:/Users/Rio/.codex/worktrees/impact-r152 (branch sandbox/r152-impact2026). Folder content unchanged except for two things kept out of git:
  - the 252 per-frame reconstruction arrays under results/20x/reconstruction, results/50x_calibrated/reconstruction and results/50x_shared_bank/reconstruction (2.66 GB) are in the release r152-impact2026-reconstructions-20261028, with their original paths; each frame_XXXX.json receipt beside them still names its array.
  - poster_build/node_modules was a junction into the Codex app's own bundled Node runtime (C:/Users/Rio/.cache/codex-runtimes/...), not an installed project dependency, and there is no package.json. The poster_build/*.mjs scripts therefore only ran inside that tool; the finished PPTX/PDF/PNG in poster_final are the deliverable.
