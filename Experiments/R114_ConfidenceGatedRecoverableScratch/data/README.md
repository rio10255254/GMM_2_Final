# R114 data package

This directory is a non-destructive view over the verified R107/R109 clear
target package.  The 5,512 existing target, mask and SDF arrays are referenced
in place and are never copied or edited.

`data_contract.json` fixes the target counts, replacement policy, batch
composition and per-scene loss normalization.  `dynamic_domains.json` records
the additional synthetic microscopy ranges.  Real SEM, HS100MG and JunHua
pixels are validation-only.

Run `scripts/prepare_data.ps1` without arguments for the safe dry run.  It:

1. verifies the immutable source hash and all source array references;
2. builds a planned 5,000 + 512 logical manifest without materializing the
   supplemental formal package;
3. makes only fifteen 8x-supersampled examples under `data/dry_run`;
4. builds deterministic batch schedules for batch sizes 12 and 16; and
5. runs the independent data validator.

Formal supplemental materialization is intentionally not the default.  It is
available through `prepare_data.py --mode materialize` after the controller
probe accepts the data contract.  That command writes only inside this R114
directory and still references the original arrays in place.
