# Lab Training Data Style Audit

- training_root: `LabSystem_MOSR\Training_Data\r55_source_style_rebuild`
- sample_per_package: `0` (`0` means all pairs)
- discovered_packages: `23`
- discovered_pairs: `51654`
- sampled_pairs: `51654`

## Verdict

No package crossed the risky-package threshold in this audit.

## High-Risk Packages

| package | pairs | sampled | high | medium | problem frac | mean lbl saturation | flags |
|---|---:|---:|---:|---:|---:|---:|---|
| none | 0 | 0 | 0 | 0 | 0 |  |

## Medium / Mixed Packages

| package | pairs | sampled | high | medium | low | flags |
|---|---:|---:|---:|---:|---:|---|
| none | 0 | 0 | 0 | 0 | 0 |  |

## Files

- package summary: `package_style_summary.csv`
- sampled pair metrics: `pair_style_sample_metrics.csv`
- worst-case visual sheet: `worst_style_contact_sheet.png`

## Audit Rules

- High risk: label is hard binary/CAD-like, has very weak source-label correspondence, or shape/read errors.
- Medium risk: label contrast/saturation differs strongly from source, but not enough to prove a broken pair.
- Low risk: label keeps a source-like grayscale style under these checks.
- Package is listed as risky when high-risk samples exceed 10% or high+medium samples exceed 25%.
