# Recent Lab GMF External Test Package

This package is for external GMF validation of the Lab 20250605 checkboard sequence.

Use the image_folder column in paths_for_gmf_tool.tsv as the input folder for each external GMF run. Put the returned GMF_score.txt into the matching score_folder column.

Important:
- Do not rename or remove BMP files.
- All cases are intended to have the same 51 BMP filenames.
- Sort by filename in the external GMF software.
- This package is exploratory; it does not replace the formal main-project GMF baseline process.

Case guide:

| Case | Meaning |
|---|---|
| 00_raw_input | Original Lab checkboard sequence |
| 01_lab_r40_best_tradeoff_control | Earlier Lab control reconstruction |
| 02_lab_r51_mixed_psf_best_tradeoff | R51 mixed-PSF best checkpoint |
| 03_lab_r52_stability_latest | R52 latest checkpoint |
| 04_lab_r53_realistic_best_tradeoff | R53 best checkpoint |
| 05_lab_r53_realistic_latest | R53 latest checkpoint |
| 06_lab_r54_edgeband_epoch020 | R54 local edge-band probe checkpoint |
| 07_lab_r55_source_style_best_tradeoff | R55 best checkpoint |
| 08_lab_r55_source_style_latest | R55 latest checkpoint |
| 09_lab_r56_label_core_repair_best_tradeoff | R56 best checkpoint |
| 10_lab_r56_label_core_repair_latest | R56 latest checkpoint |
