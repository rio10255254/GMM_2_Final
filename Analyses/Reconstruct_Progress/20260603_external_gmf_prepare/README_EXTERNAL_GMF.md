# 20260603 external GMF preparation

This folder packages the 20260603 sample reconstructions for an external GMF
tool run.

Important limitation: this is not a formal baseline-level GMF validation. The
available 20260603 data has 11 timestamped sample images only. It is not the
standard three-pitch ring sequence used by the project for comparable external
GMF numbers.

## What is included

| Folder | Meaning |
|---|---|
| `00_raw_input/bmp/` | Original 20260603 camera images |
| `01_r39r40_default/bmp/` | R39R40_avg_a025 default reconstruction |
| `02_reg300_current_best/bmp/` | Current best temporary internal tuning from the conservative physics sweep |
| `03_combo_reference/bmp/` | COMBO formal-baseline reconstruction on the same 11 images |
| `04_psf_bypass_extreme/bmp/` | Extreme PSF-minimum/bypass reconstruction for sanity comparison |

`paths_for_gmf_tool.tsv` lists the image folder and score-output folder for
each case.

## How to run the external tool

1. For each case, use the corresponding `bmp` folder as the input image folder
   in the external GMF tool.
2. Save the external tool output as `GMF_score.txt`.
3. Put each score file in the matching folder under `_gmf_scores/`.

Expected score locations:

| Case | Put `GMF_score.txt` here |
|---|---|
| `00_raw_input` | `_gmf_scores/00_raw_input/GMF_score.txt` |
| `01_r39r40_default` | `_gmf_scores/01_r39r40_default/GMF_score.txt` |
| `02_reg300_current_best` | `_gmf_scores/02_reg300_current_best/GMF_score.txt` |
| `03_combo_reference` | `_gmf_scores/03_combo_reference/GMF_score.txt` |
| `04_psf_bypass_extreme` | `_gmf_scores/04_psf_bypass_extreme/GMF_score.txt` |

Then run:

```powershell
python Analyses\Reconstruct_Progress\20260603_external_gmf_prepare\analyze_external_gmf_scores.py
```

The script writes:

- `gmf_exploratory_summary.json`
- `gmf_exploratory_summary.md`

## How to interpret it

Use this only as same-sample exploratory evidence: it can show whether the GMF
tool tracks one reconstruction more stably than another on these 11 images.

Do not compare these values directly to the official COMBO/R39R40 external GMF
numbers. For a formal comparable GMF result, capture the standard three pitch
sequences and run the existing project external-compare workflow.
