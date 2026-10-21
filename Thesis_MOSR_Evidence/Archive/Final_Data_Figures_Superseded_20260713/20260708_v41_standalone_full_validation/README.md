# Chapter 6 Visual Reconstruction and CD Validation Package

This folder centralizes the first two Chapter 6 experiment groups:

1. visual reconstruction comparison on the 100MG sample and concentric Step sample;
2. center-nine 100MG pillar CD comparison against SEM-derived diameter truth.

## Main Outputs

- Independent visual crops: `images/`
- CD measurement tables: `tables/100mg_center9_cd_raw_combo_r61_v41.csv` and `tables/100mg_center9_cd_error_summary.csv`
- Thesis-ready CD figures: `figures/100mg_center9_cd_line.png`, `figures/100mg_center9_cd_line_zoom_raw_r61_v41.png`, `figures/100mg_center9_cd_error_bar.png`, `figures/100mg_center9_cd_table.png`

## Method Notes

- All 100MG CD values use the same nine pillar centers selected from the raw-template feature table.
- The SEM reference is read from the SEM-derived 36-record diameter table.
- The V41 reconstruction is generated in this package with PSF disabled during inference.
- The COMBO comparison uses the PSF-bypass image because the PSF-on version was previously observed to over-expand the measured pillars.

## Quick Result

- Lowest mean absolute CD error in this focused center-nine test: `raw` at `18.55 nm`.
