# LabSystem_MOSR Experiments Index

Last updated: 2026-06-18

| Experiment | Status | Purpose |
|---|---|---|
| R39_ShapeGeneralization | completed | Lab shape generalization package and formal Lab R39 training baseline |
| R40_MicroscopyFeatureCoverage | completed | Lab microscopy-feature package and formal Lab R40 training baseline |
| R46_CornerAwareFineTune | completed; not promoted | First checkboard/corner focused Lab fine-tune |
| R47_RealisticBoundaryGeneralization | completed; not promoted | Larger realistic boundary expansion; failed real checkboard corner validation |
| R48_RealCornerTransfer | completed; not promoted | Real Lab corner transfer with geometry sidecars; 200-epoch training completed but real checkboard corner validation failed |
| R49_CADAnchorRealGeometry | completed; not promoted | Real CAD-anchor checkboard geometry transfer; 100-epoch training completed but real checkboard corner validation failed |
| R50_PSFControlDiagnosis | completed diagnostic | PSF/degradation control check; formal BADS is usable but too soft as the only Lab checkboard-corner blur truth |
| R51_BlurSourceProbe | completed probe; not promoted | Gaussian / weak-BADS / mixed-PSF short training probe; mixed-PSF improved median corner shift but did not pass large-shift stability |
| R52_CornerStabilityGuard | completed; not promoted | Mixed-PSF plus real-corner stability data; 100-epoch formal run completed, but real checkboard corner gate failed |
| R53_RealisticDatasetCalibration | completed; not promoted | Rebalanced Lab dataset with main-project-like shape/micro/real-background mix, mixed-PSF corners, and masked real CAD anchors; 100-epoch scratch run completed, but real checkboard corner gate failed |
| R54_GeometryRootCauseProbe | completed probe; not promoted | Root-cause probe plus edge-band masked small-overfit: local CAD edge fit succeeded, but real checkboard validation failed and the R54 checkpoint is not usable |
| R55_SourceStyleRealisticTraining | completed locally; external GMF pending | Source-style repair validation: best_tradeoff passed the real 20250605 checkboard corner gate versus Lab R40; latest failed from overtraining/oversmoothing |
| R56_LabelCoreRepairTraining | completed; not adopted | Label-core repaired R53/R55 source-style package; 50-epoch training completed, but real checkboard corner gate failed because tail shift and large-shift rate worsened versus R55 best |
