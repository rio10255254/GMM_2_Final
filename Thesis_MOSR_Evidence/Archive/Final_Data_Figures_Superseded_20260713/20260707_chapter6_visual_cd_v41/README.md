# Chapter 6 - 100MG Visual Reconstruction and CD Validation

This folder is the cleaned Chapter 6 evidence package for the 100MG / concentric-sample reconstruction check.

It now keeps only the current useful outputs in the main folder. Older center-9 results, single-line profile drafts, duplicated reconstruction runtime folders, logs, and bulky regenerable raw profile tables were moved to `_archive_superseded_20260707/`.

## What To Use

### 1. Main CD Result

Use these for the 100MG center 6x6 SEM comparison:

- `tables/100mg_center36_pillar_via_cross_section_cd_raw_v41_summary.csv`
- `tables/100mg_center36_pillar_via_cross_section_cd_raw_v41_wide.csv`
- `figures/center36_cd_maps/`

These compare Raw and V41 against the SEM Excel layout blocks for the closest center 36 pillars and 36 vias.

### 2. Detailed Profile Evidence

Use these to explain why the boundary result is believable:

- `figures/center36_detail_profiles/`
- `figures/center36_edge_aligned_profiles/`
- `tables/center36_detail_profiles/100mg_center36_detail_profile_catalog.csv`
- `tables/center36_edge_aligned_profiles/100mg_center36_edge_aligned_summary.csv`

The detail-profile figures show each row as six separate cells, so Raw and V41 do not hide each other. The edge-aligned figures average all 36 boundaries and show that V41 has a narrower boundary transition than Raw.

### 3. Representative Local Views

Use these when a slide or thesis paragraph needs real image examples:

- `figures/center36_representative_zooms/`
- `figures/center36_representative_zooms/individual_crops/`
- `tables/100mg_center36_representative_zoom_catalog.csv`

These examples include best improvement, median improvement, and largest remaining V41 error cases for pillars and vias.

### 4. Visual Reconstruction Crops

Use these for side-by-side visual comparison:

- `images/`

This includes Raw, COMBO PSF-bypass, R61 v16, and V41 crops for the 100MG and concentric samples.

### 5. Source Inputs and Final Reconstruction

Keep these for traceability:

- `inputs/`
- `reconstruction_runs/final_v41_psfoff/`

The reconstruction folder now keeps one clean copy of the final V41 PSF-off output for 100MG and one for the concentric sample.

## Scripts

The active scripts are in `scripts/`:

- `measure_center36_pillar_via_raw_v41_cross_section.py`: recalculates the center 6x6 Raw/V41 CD comparison and writes the CD maps.
- `make_center36_row_profiles_and_zooms.py`: regenerates the separated profile panels, edge-aligned profile figures, row overview figures, and representative zooms.
- `measure_cd_by_cross_section.py`: helper used by the center 6x6 CD script.
- `make_chapter6_visual_cd_assets.py`: image-reading and asset helper. Its old center-9 standalone outputs are not the current main evidence.

Recommended rerun order:

```powershell
python .\scripts\measure_center36_pillar_via_raw_v41_cross_section.py
python .\scripts\make_center36_row_profiles_and_zooms.py
```

## Current Reading

- Pillars: V41 is closer than Raw for all 36 center pillars.
- Vias: V41 is closer than Raw for 35 of 36 center vias, but the via result has visible local outliers and should be described more cautiously.
- Edge profiles: V41 has a narrower boundary transition than Raw for both pillar edges and both via edges. The pillar improvement is much stronger and cleaner than the via improvement.

## Archive

`_archive_superseded_20260707/` is not part of the main thesis evidence path. It only keeps older or duplicated material so nothing is lost during cleanup.
