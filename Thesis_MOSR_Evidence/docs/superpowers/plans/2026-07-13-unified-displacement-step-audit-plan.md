# Unified Displacement Step Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify a blind, timestamp- and Raw-motion-defined audit of all four thesis displacement sequences.

**Architecture:** A reusable audit module validates source mappings, segments acquisition sessions, re-anchors the same nine SEM identities, runs locked boundary and independent local 2D tracking, and produces eligibility without reading V42 measurements. A packaging layer joins V42 only after the pair list is locked and exports the candidate thesis evidence.

**Tech Stack:** Python 3.12, OpenCV, NumPy, pandas, Matplotlib, pytest.

---

### Task 1: Lock source and eligibility behavior

**Files:**
- Create: `Final_Data_Figures/20260712_sem_anchored_center9_validation/tests/test_unified_displacement_audit.py`
- Create: `Final_Data_Figures/20260712_sem_anchored_center9_validation/scripts/displacement_audit_core.py`
- Create: `Final_Data_Figures/20260712_sem_anchored_center9_validation/scripts/audit_all_displacement_sequences.py`

- [ ] Write failing tests for exact four-sequence scope and exact nine identities.
- [ ] Write failing tests for timestamp-only session boundaries.
- [ ] Write failing tests proving V42 values, missingness, identities, and validity gates cannot alter Raw eligibility.
- [ ] Write failing tests for complete pair reconciliation and exclusion reasons.
- [ ] Test every frozen Raw pillar, step, and continuity gate independently.
- [ ] Test candidate counts for Raw-eligible, V42-evaluable, and paired-comparison steps.
- [ ] Test improved/worse/tie classification at the 1.0 nm boundaries.
- [ ] Implement source validation, session detection, and blind eligibility.

### Task 2: Re-anchor and measure all four sequences

- [ ] Implement the frozen whole-frame Raw anchor rule, uniqueness check, and no-retry failure behavior.
- [ ] Test anchor x/y refinement, border failure, equal-peak failure, and invalid-curvature integer fallback.
- [ ] Test a session whose observed start differs from nominal cumulative motion.
- [ ] Prove anchor identities and offsets cannot change when V42 changes.
- [ ] Run locked Raw-guided boundary tracking inside every session.
- [ ] Run independent local 2D tracking for Raw and V42.
- [ ] Test previous-frame templates, exact template/search formulas, signed displacement, median aggregation, and deterministic invalid-pillar advancement.
- [ ] Export all adjacent pairs, including cross-session pairs.
- [ ] Verify only the predeclared frame-27/frame-31, frame-1, and frame-15/frame-45/frame-46 checks.
- [ ] Use only the predeclared Raw edge-phase CSV as a diagnostic reference.

### Task 3: Sensitivity and candidate populations

- [ ] Compute 20%, 25%, and 30% tolerance sensitivity.
- [ ] Export full within-session, platform-valid, and regular-cadence populations.
- [ ] Prove Raw and V42 use the same selected pairs.
- [ ] Test sample-SD `ddof=1`, per-step robust disagreement, unweighted sequence means, missing values, and all required candidate fields.
- [ ] Compare result direction across sensitivity levels.
- [ ] Build the candidate four-sequence thesis table from fixed `platform_valid_25pct` only.
- [ ] Classify standard-deviation and local-consistency direction as improved, worse, or tie across all tolerances.

### Task 4: Visual evidence and report

- [ ] Generate per-sequence timing and 2D motion traces.
- [ ] Generate selected-step Raw/V42 traces and exclusion-reason figures.
- [ ] Generate cross-sequence stability and local-consistency figures.
- [ ] Write a Traditional Chinese audit report with exact exclusions and claim limits.
- [ ] Visually inspect every final figure.

### Task 5: Verification

- [ ] Independently recompute headline values from exported pair tables.
- [ ] Inventory and hash every protected existing file before execution and require identical hashes afterward.
- [ ] Fail if the build changes any inventoried file outside the two new output folders.
- [ ] Run focused tests and the complete validation suite.
- [ ] Scan the candidate package for the exact four approved sequences only.
