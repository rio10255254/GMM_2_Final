# R81 manifest

## Reused immutable evidence

- Paired training package: `V42_SoftLabelSNR_FullStandalone_20260709`
- Existing thesis checkpoint: MOSR V42
- Locked formal sequences: `sequence_center9_50x20x.json`
- Raw-only pair eligibility: `raw_eligibility_locked_before_v42.csv`
- Measurement core: R80 ACM + maximum-gradient inflection + reference circles

## New outputs

- `results/training/<model>`: checkpoint, history, validation summary
- `results/evaluation/<model>`: locked-frame reconstructions, reference-circle tables, and manifest
- `results/training_frame_overlap_audit.json`: physical-frame overlap disclosure
- `results/tables/thirteen_model_measurement_summary.csv`: formal learned-model table
- `reports/R81_RESULTS.md`: traceable readout used by the thesis revision

## Third-party source

`third_party/pft_sr` contains the official PFT-SR architecture source and CUDA
operator used for the 2025 comparison.  Its upstream license is retained.  The
operator was compiled for the local Python 3.12, PyTorch 2.3, CUDA 12.6, and
compute capability 8.6 environment.

`third_party/ucan_official` is the official UCAN repository used to verify the
CVPR 2026 architecture. `third_party/ucan` contains the unchanged architecture
body plus a local registry shim and the retained upstream license for the x1
grayscale adaptation. The locked upstream revision is
`b812c0adb8ce70d442973db5c87bab7d1e8c3333` (2026-04-17).
