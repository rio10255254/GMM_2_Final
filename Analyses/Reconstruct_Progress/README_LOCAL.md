# Local Reconstruction Output Index

This folder is local-only scratch output. It is intentionally ignored by git.

## 20260603 New-System Sample Checks

Source images:

- `C:\Users\Rio\Desktop\20260603`

Main output groups:

- `20260603_R39R40_avg_a025`:
  Original R39R40_avg_a025 reconstruction of all 11 BMP inputs.
- `20260603_COMBO_reference`:
  COMBO reference reconstruction for visual comparison.
- `20260603_R39R40_model_internal_sweep`:
  First internal-setting sweep. Lowering force alone was not helpful.
- `20260603_R39R40_model_internal_sweep_reg`:
  Conservative physics sweep. `reg300_default` is the current best local visual tradeoff.
- `20260603_R39R40_psf_min_sweep`:
  PSF-minimum and PSF-bypass checks. Removing PSF influence did not improve visual fidelity.

Useful comparison sheets:

- `20260603_R39R40_avg_a025/reconstruct_progress_best_tradeoff_in_20260603_20260511_151845/analysis/r39r40_vs_combo_edge_crop_contact_sheet.png`
- `20260603_R39R40_model_internal_sweep_reg/reconstruct_progress_best_tradeoff_in_20260603_20260511_151845/analysis/reg_extended_representative_contact_sheet.png`
- `20260603_R39R40_psf_min_sweep/reconstruct_progress_best_tradeoff_in_20260603_20260511_151845/analysis/psf_min_sweep_representative_contact_sheet.png`

Current local takeaway:

- Original R39R40 is clearer than the input but can look over-corrected on the new capture system.
- Lowering the reconstruction force alone made the output harder, not more faithful.
- Conservative physics inversion (`reg300_default`) is the best temporary setting tested so far.
- Minimizing or bypassing PSF made the output less natural, so PSF is not simply noise in this checkpoint.

This is not a formal experiment report. It should only become formal if the project owner decides the 20260603 new-system sample work should be promoted into an experiment or documented evaluation.
