# Unified Displacement Step Audit Design

## Goal

Re-audit the four thesis displacement sequences using the same SEM-anchored center-nine pillar identities, then produce a defensible candidate population of physically valid displacement steps without using V42 performance to decide inclusion.

## Scope

The audit covers exactly:

- `50x_x_0p5um`
- `50x_x_1um`
- `20x_0p5um`
- `20x_1um`

Every sequence uses pillar identities 22-24, 28-30, and 34-36. Existing full-audit and thesis outputs remain unchanged. New outputs are additive under `diagnostics/unified_displacement_step_audit` and `thesis_50x_20x/displacement_screened_candidate`.

## Blind eligibility rule

Eligibility is determined before V42 values are joined. A pair is eligible at the primary 25% tolerance only when all of the following are true:

1. Both frames belong to the same acquisition session. A timestamp gap greater than 60 seconds starts a new session.
2. Raw local two-dimensional tracking measures signed x displacement within 25% of the nominal command magnitude.
3. Absolute Raw y displacement is at most 25% of the nominal command magnitude.
4. Raw local matching retains the same nine identities with minimum normalized match score at least 0.95.
5. The locked Raw boundary measurement and independent Raw local two-dimensional measurement agree within 25% of the nominal command magnitude.
6. Raw boundary tracking retains all nine pillar identities and passes the frozen Raw validity gates below.

The complete pair audit records every adjacent pair and every failed reason. No pair is deleted from the audit table.

The frozen boundary configuration is read unchanged from `config/sequence_center9.json`: polarity, radius, pitch, search radius, minimum seven valid pillars, and minimum edge strength 2.0. Each radius-at-least-3 pillar needs at least three valid horizontal chords; edge strength must be at least 2.0; chord-center MAD must be at most `max(0.35 px, 0.15 * radius_px)`; measured center must remain inside the configured search radius; width and expected-chord geometry checks in `pillar_motion_core.measure_pillar_x` must pass. Step outlier rejection uses `max(3 * 1.4826 * displacement_MAD, 0.45 * search_radius_px)`. Step continuity requires absolute consensus error from the expected signed step below half pitch. Formal Raw eligibility additionally requires all nine pillar identities valid in both adjacent frames and in the step.

V42 is joined only after this Raw eligibility table has been written and hashed. V42 receives a separate `v42_evaluable` flag and failure reason. V42 values, missingness, identities, or validity gates can never alter Raw eligibility or remove a pair from the audit. Every summary reports `raw_eligible_count`, `v42_evaluable_count_within_raw`, and `paired_comparison_count`; any difference remains visible rather than silently narrowing the Raw population.

## Session handling

Timestamp session membership is independent of image content. At each session start, Raw frame 0 supplies one fixed asymmetric anchor patch centered on the nine-pillar centroid, with square side `round(7 * pitch_px)` so the complete pillar block and surrounding corner context are included. OpenCV normalized correlation searches the entire valid Raw session-start frame and selects the global maximum; quadratic three-point refinement supplies the subpixel peak. The match score must be at least 0.80 and exceed the best peak outside a one-pitch exclusion zone by at least 0.01. This directly locates the observed session start and never counts cross-session transitions as commanded motion. The resulting absolute x/y offset shifts the unchanged nine identities. No alternative setting or manual identity replacement is allowed. A failed anchor remains recorded and makes that session Raw-ineligible rather than triggering retries with different parameters.

Boundary tracking and local two-dimensional tracking restart inside each successfully anchored session. V42 uses the Raw anchor unchanged. Cross-session pairs remain visible but are never interpreted as commanded stage steps.

For both session anchoring and consecutive local tracking, subpixel refinement is applied independently to x and y. At integer peak `(x0, y0)`, x uses the row values `(L, C, R) = score[y0, x0-1:x0+2]` and `delta_x = 0.5 * (L - R) / (L - 2C + R)`; y uses the analogous column values. A finite negative denominator below `-1e-12` is required and the offset is clipped to `[-1, 1]`. Invalid curvature deterministically falls back to zero offset. A peak lacking either neighbor fails anchoring; for local tracking it makes that pillar invalid for the step. Equal global maxima fail the anchor through the 0.01 uniqueness-margin rule.

Consecutive Raw local 2D tracking is frozen as follows. For every session and every pillar, the template comes from the immediately previous Raw frame at that pillar's previous tracked position. Template half-size is `ceil(radius_px + 2)`. The current-frame prediction is previous position plus configured `expected_signed_dx_px` in x and zero in y. A square search adds `ceil(max(5, 0.25 * radius_px))` pixels on each side. OpenCV normalized correlation and the same independent x/y refinement locate the current center. Signed displacement is current minus previous position. A pillar is locally valid only when its peak is interior and score is at least 0.95. The step's Raw local x and y values are the medians of the same nine pillar displacements, and formal eligibility requires all nine locally valid. Invalid pillars still advance deterministically to their integer peak position so the next frame is auditable; no retry, alternate radius, or identity substitution is allowed. V42 is later tracked with the same formulas and Raw-locked session anchors, but does not participate in eligibility.

## Populations

Each sequence exports three populations:

- `all_within_session`: every adjacent pair inside a timestamp-defined acquisition session.
- `platform_valid_25pct`: pairs passing the blind primary rule.
- `platform_valid_regular_cadence`: primary-valid pairs whose timestamp gap is at most 10 seconds.

The 10-second regular-cadence view is secondary and explicitly labeled. The complete within-session result remains visible.

The candidate thesis table is fixed in advance to `platform_valid_25pct`. `all_within_session` and `platform_valid_regular_cadence` are disclosed comparisons only and can never replace the candidate population after V42 is viewed.

## Sensitivity and cross-validation

The motion and cross-method tolerances are recomputed at 20%, 25%, and 30%. For both signed-step standard deviation and mean within-grid disagreement, an absolute Raw-V42 difference of at most 1.0 nm is `tie`; otherwise V42 lower is `improved` and V42 higher is `worse`. A conclusion is called robust only when this direction does not change across all three tolerances. Raw and V42 are compared on the exact same locked pair list when V42 is evaluable; Raw eligibility itself is unchanged. The existing boundary tracker is cross-checked against independent local two-dimensional tracking.

Formal predeclared event checks are limited to: `50x_x_0p5um` pairs ending at frames 27 and 31 must be cross-session; `50x_x_1um` pair ending at frame 1 must be cross-session; and `20x_0p5um` pairs ending at frames 15, 45, and 46 must fail the 25% Raw motion rule. The only permitted edge-phase reference is `Analyses/20260704_20x_5x_analysis/phase_algorithm_final_summary/edge_phase_primary_gap30_summary_um.csv`, Raw rows only, and it is diagnostic rather than an eligibility input.

## Metric definitions

Metrics are computed separately for each sequence, population, and case; sequences are never pooled or weighted together for a headline value. A valid boundary step first takes the median signed x displacement across the retained pillar identities. For a population with `n >= 2` paired-evaluable steps, signed-step standard deviation is the sample standard deviation (`ddof=1`) of those step medians in micrometers, multiplied by 1000 to report nanometers. With fewer than two steps it is missing.

Within-grid disagreement is computed per step as `1.4826 * median(abs(pillar_dx_px - step_median_dx_px)) * object_um_per_px * 1000`. The sequence/population summary is the unweighted arithmetic mean of this value across the same paired-evaluable selected steps. Missing V42 steps are excluded only from paired metrics, while Raw-eligible, V42-evaluable, and paired counts remain separate columns.

Candidate tables must include: sequence, nominal step, total adjacent pairs, within-session pairs, Raw-eligible count, V42-evaluable-within-Raw count, paired count, coverage percentages, Raw/V42 mean signed step, Raw/V42 signed-step sample SD, Raw/V42 mean within-grid disagreement, both Raw-V42 differences, 1 nm direction classifications, and excluded-reason counts.

## Outputs

- One row per adjacent pair with timestamps, session IDs, Raw 2D x/y motion, boundary measurements, quality fields, eligibility, and exclusion reasons.
- Per-sequence and cross-sequence population summaries.
- Tolerance sensitivity tables.
- Retained and excluded step lists.
- Timestamp/motion traces, selected-step traces, Raw/V42 comparison figures, and selection-reason figures.
- A Traditional Chinese report separating full evidence, candidate thesis evidence, and claim limits.
- A candidate four-sequence thesis table. It does not overwrite the existing thesis package.

Before execution, a fixed inventory and SHA-256 digest are recorded for every existing file under `cd`, `displacement`, and `thesis_50x_20x`, plus the root `REPORT.md`, `manifest.json`, and `reproducibility_sha256.csv`. Files already present under the two new output folders are excluded because those folders are intentionally rebuilt. Every inventoried file must retain the same digest after execution, and the build fails otherwise.

## Claim limits

The audit measures repeatability and physical consistency relative to commanded motion. The stage command is not independent position truth. A timing- or motion-defined subset may support a conditional stability claim only when the full population, rule, and excluded pairs are disclosed beside it.
