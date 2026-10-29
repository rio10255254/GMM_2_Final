# V41-Standalone Full Validation Report

## Scope
This package validates the long-trained V41-Standalone checkpoint with PSF disabled during inference.

## Checkpoint
- Weight: `Thesis_MOSR_Evidence/LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_v41_standalone_long_standalone_full_e16_20260708_100223_20260708_100251/weights/best_tradeoff.pth.tar`
- Training finished at 16/16 epochs; best epoch was 16.
- Training summary: `[SUMMARY] Best epoch = 16, tradeoff = 150.6067, gmf_obj = 150.8683, best_val_rec = 0.029687, best_val_ssim = 0.7068`

## CD Validation: 100MG Center 6x6 Pillars and Vias
| Feature | Raw mean error nm | Old V41 mean error nm | V41-Standalone mean error nm | vs Raw | vs Old V41 |
|---|---:|---:|---:|---:|---:|
| pillar | 81.26 | 59.55 | 64.60 | 20.50% | -8.47% |
| via | 314.11 | 235.64 | 243.14 | 22.59% | -3.18% |

Interpretation: V41-Standalone improves CD error versus Raw for both pillars and vias, but old V41 remains slightly better on this CD metric.

## Displacement Validation: Recommended ROI Profile
| Dataset | Group | ROI profile | Raw std um | Old V41 std um | V41-Standalone std um | Best case | vs Raw | vs Old V41 |
|---|---|---|---:|---:|---:|---|---:|---:|
| 20260702_100MG | x_1um | fixed_roi | 0.009391 | 0.009424 | 0.009410 | r61 | -0.21% | 0.15% |
| 20260702_100MG | x_0p5um | fixed_roi | 0.052039 | 0.052028 | 0.052018 | r61 | 0.04% | 0.02% |
| 20260704_20x_5x | 20x_1um | fixed_roi | 0.025569 | 0.025356 | 0.025335 | v41_standalone | 0.92% | 0.09% |
| 20260704_20x_5x | 20x_0p5um | fixed_roi | 0.076249 | 0.076227 | 0.076242 | v41_old | 0.01% | -0.02% |
| 20260704_20x_5x | 5x_1um | shape_aware_square_roi | 0.158455 | 0.157068 | 0.158359 | v20 | 0.06% | -0.82% |
| 20260704_20x_5x | 5x_0p5um | shape_aware_square_roi | 0.013996 | 0.013415 | 0.013935 | v41_old | 0.44% | -3.88% |

Interpretation: using the appropriate ROI profile, V41-Standalone is slightly better than Raw in five of six displacement groups, but the gain is small and it is not consistently better than old V41.

## Important Caveats
- Fixed ROI fails badly on 5x sequences for reconstructed images; the shape-aware square ROI is the appropriate reading for 5x.
- The open GMF-like method is useful for internal comparison, but it is still a measurement algorithm choice; thesis wording should avoid claiming universal superiority from this alone.
- CD results are stronger than displacement results for this new long-trained checkpoint.

## Boundary-Sensitive ROI Displacement Addendum
The thesis-oriented displacement readout was rerun with the boundary-sensitive ROI method for Raw, old V41, and V41-Standalone. This is the preferred displacement analysis for showing boundary-driven reconstruction advantage; the GMF-like readout above remains a supplemental internal check.

Main all-step findings:
- 100MG x_1um: old V41 improves step stability by 16.75% vs Raw; V41-Standalone improves by 16.17%.
- 100MG x_0p5um: both V41 versions are nearly tied and slightly better than Raw.
- 20x_1um: both V41 versions improve stability modestly vs Raw.
- 5x groups are mixed; they should be treated as limitation / robustness evidence, not as the main advantage claim.

## Main Files
- CD comparison table: `Thesis_MOSR_Evidence/Final_Data_Figures/20260708_v41_standalone_full_validation/tables/cd_center36_old_v41_vs_v41_standalone_summary.csv`
- Recommended displacement table: `Thesis_MOSR_Evidence/Final_Data_Figures/20260708_v41_standalone_full_validation/tables/displacement_recommended_profile_summary.csv`
- Boundary-sensitive ROI V41 comparison: `Thesis_MOSR_Evidence/Final_Data_Figures/20260708_v41_standalone_full_validation/boundary_sensitive_roi_v41_compare`
- Summary figures: `Thesis_MOSR_Evidence/Final_Data_Figures/20260708_v41_standalone_full_validation/figures/validation_summary`
- Step trace figures: `Thesis_MOSR_Evidence/Final_Data_Figures/20260708_v41_standalone_full_validation/figures/validation_summary/step_traces`
