# Visual Evidence

This directory holds a very small number of curated side-by-side comparison
sheets.

The goal is to make important visual verdict differences reviewable in GitHub
without checking in large raw BMP collections.

## What Is Being Compared

Each sheet compares the same filename, on the same `0.8px` battlefield case,
across the same four lines:

- `R26`
- `Round30 baseline`
- `Round31 regression`
- `Round32 fail`

This keeps the comparison fair:

- same case
- same view
- same battlefield
- same four lines

## Why PNG Sheets Instead Of Raw BMPs

The original BMPs are much larger and much harder to review in GitHub.

These sheets are intentionally:

- smaller
- labeled
- easier to scan in pull requests and markdown
- better for side-by-side visual comparison

## Files

- `comparison_0p8px_case_01.png`
  - compares `VisionTop_20251029185330879.bmp`
- `comparison_0p8px_case_02.png`
  - compares `VisionTop_20251029185655191.bmp`

## Curation Rule

Do not add raw reconstruction sets here.

Only add visual evidence when it is:

- compact
- directly comparable
- clearly labeled
- tied to an important baseline / regression / fail verdict
