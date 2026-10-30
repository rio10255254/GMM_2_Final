# Representative Multiscale External Validation

Correct representative checkpoint used for this batch:

- `Experiments/Training_Runs/training_progress_GESR_v1_v5_ST0p08_SWP_mgc_20260310_120940/weights/best_tradeoff.pth.tar`

Correct reconstruction root for this batch:

- `Experiments/Legacy/organized_20260310/external_validation/representative_multiscale/reconstructions/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260310_120940`

Datasets reconstructed with `select-mode=odd`:

- `Pitch1um_Y_100`: `101` images
- `Pitch0.1um_Y_60`: `61` images
- `Pitch0.01um_Y_40`: `41` images

Correct output folders:

- `Experiments/Legacy/organized_20260310/external_validation/representative_multiscale/reconstructions/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260310_120940/pitch1um_y_100_odd`
- `Experiments/Legacy/organized_20260310/external_validation/representative_multiscale/reconstructions/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260310_120940/pitch0p1um_y_60_odd`
- `Experiments/Legacy/organized_20260310/external_validation/representative_multiscale/reconstructions/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260310_120940/pitch0p01um_y_40_odd`

Batch manifest:

- `Experiments/Legacy/organized_20260310/external_validation/representative_multiscale/reconstructions/batch_manifest.json`

Batch logs:

- `Experiments/Legacy/organized_20260310/external_validation/representative_multiscale/logs/representative_recon_retry_20260310_131416.out.log`
- `Experiments/Legacy/organized_20260310/external_validation/representative_multiscale/logs/representative_recon_retry_20260310_131416.err.log`

Ignore this earlier accidental run for representative testing:

- `Experiments/Legacy/organized_20260310/external_validation/representative_multiscale/reconstructions/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260307_135625`

Reason:

- At that time, the inference script incorrectly prioritized `MANUAL_WEIGHTS_PATH` over CLI `--weights`.
- This bug has been fixed in:
  - `Model/GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py`
