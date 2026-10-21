# Thesis 50x/20x and 50x 0.5 um Session Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a thesis-only 50x/20x package and correct the 50x 0.5 um analysis using timestamp-defined acquisition sessions.

**Architecture:** A focused session-analysis module reads the frozen mapping, sequence configuration, and Raw/V42 frames. It detects timestamp gaps independently of image quality, re-anchors the same nine identities at each session start, and exports all within-session steps. A separate thesis-packaging module filters out 5x and substitutes the corrected 50x 0.5 um result without modifying the full audit archive.

**Tech Stack:** Python 3.12, pandas, NumPy, OpenCV, Matplotlib, pytest.

---

### Task 1: Timestamp-defined 50x 0.5 um sessions

**Files:**
- Create: `Final_Data_Figures/20260712_sem_anchored_center9_validation/scripts/analyze_50x_0p5um_sessions.py`
- Create: `Final_Data_Figures/20260712_sem_anchored_center9_validation/tests/test_50x_0p5um_sessions.py`

- [x] Write failing tests for three timestamp-defined sessions, exactly two excluded cross-session pairs, and identical boundaries for thresholds from 45 through 180 seconds.
- [x] Prove that changing image arrays or measurement columns cannot change session membership.
- [x] Verify tests fail because the session module is missing.
- [x] Implement mapping validation, gap detection, two-dimensional session re-anchoring, and within-session tracking.
- [x] Export all 50 adjacent pairs: 48 retained and two excluded with timestamps, gap seconds, global frame indices, and reason `cross_acquisition_session`.
- [x] Export diagnostics and summaries under `diagnostics/50x_0p5um_sessions`.
- [x] Run the focused test suite.

### Task 2: Thesis-only 50x/20x package

**Files:**
- Create: `Final_Data_Figures/20260712_sem_anchored_center9_validation/scripts/build_thesis_50x20x_package.py`
- Create: `Final_Data_Figures/20260712_sem_anchored_center9_validation/tests/test_thesis_50x20x_package.py`
- Create outputs under: `Final_Data_Figures/20260712_sem_anchored_center9_validation/thesis_50x_20x/`

- [x] Write failing tests proving that every 5x row, filename, caption, legend, report sentence, and manifest entry is excluded.
- [x] Require exactly `50x_x_0p5um`, `50x_x_1um`, `20x_0p5um`, and `20x_1um`, with exactly one corrected segmented 50x 0.5 um row.
- [x] Verify the corrected 50x 0.5 um summary replaces the unsegmented row.
- [x] Export four-sequence thesis tables, summary figures, and a thesis-facing report.
- [x] Record the thesis scope only in the new thesis-package manifest; do not alter the root manifest or root report.
- [x] Snapshot hashes for the protected full-audit artifacts before and after package generation and require no changes.
- [x] Verify all thesis figures and tables contain only 50x/20x material.

### Task 3: Reproducibility and final verification

- [x] Run both new entrypoints from clean processes.
- [x] Independently recompute the corrected 50x 0.5 um headline values from exported per-step CSV files.
- [x] Run the complete pytest suite.
- [x] Inspect final figures for clipping, wrong identities, and excluded-scope references.
- [x] Record source paths, session boundaries, exclusions, units, and limitations.
