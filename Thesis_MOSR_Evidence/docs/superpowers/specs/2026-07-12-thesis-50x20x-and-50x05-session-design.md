# Thesis 50x/20x Scope and 50x 0.5 um Session Design

## Goal

Create a thesis-facing evidence subset containing only 50x and 20x results, while preserving the full 5x-inclusive validation as an internal audit archive. Re-evaluate the 50x 0.5 um sequence according to acquisition-session boundaries derived only from original timestamps.

## Evidence rule

The original `input_mapping.csv` is the sole source for acquisition timestamps. A new session begins when the timestamp gap exceeds 60 seconds. Normal within-session gaps are at most 32 seconds, while the two breaks are 283 and 1321 seconds. Threshold sensitivity from 45 through 180 seconds must yield the same three sessions: frames 0-26, 27-30, and 31-50. Image content and model results are forbidden inputs to session membership.

All 50 adjacent frame pairs remain in an audit table. The two cross-session pairs are marked excluded with both timestamps, gap length, frame numbers, and the fixed reason `cross_acquisition_session`; the other 48 pairs are retained.

At each session start, the same physical center-nine identities are re-anchored by the two-dimensional image shift relative to frame 0. Raw and V42 then use identical identities, frames, gates, and Raw-guided windows within that session. Every within-session consecutive pair is retained; no result-based step selection is allowed.

## Outputs

- A 50x 0.5 um session diagnostic table, per-step table, summary, timestamp-gap figure, vertical-shift figure, and before/after comparison.
- A thesis subset containing only 50x and 20x summary tables and figures.
- A thesis-facing report that does not discuss 5x results.
- The existing `cd`, `displacement`, root report, root manifest, and root reproducibility table remain byte-for-byte unchanged as protected internal evidence. New diagnostics and thesis outputs are additive.

## Claim limits

The segmented 50x 0.5 um result supports repeatability and Raw/V42 comparison within actual continuous acquisition sessions. It does not provide independent stage-position truth. Session segmentation corrects a data-assembly error; it is not an outlier-removal rule.
