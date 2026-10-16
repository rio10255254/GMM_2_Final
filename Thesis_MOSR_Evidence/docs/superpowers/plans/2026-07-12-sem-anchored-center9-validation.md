# SEM-Anchored Center-Nine Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lock the nine pillars nearest the physical sample center to the SEM layout, then compare Raw and V42 CD and local displacement without result-based ROI selection.

**Architecture:** A new audit-safe package under `Final_Data_Figures/20260712_sem_anchored_center9_validation` reads the original SEM workbook, the existing 100MG feature measurements, and the frozen Raw/V42 displacement frames. The SEM workbook is the identity source; optical orientation is recorded per capture, and all measurements use the same pillar identities, frame pairs, and validity gates for Raw and V42.

**Tech Stack:** Python 3.12, pandas, NumPy, OpenCV, Pillow, Matplotlib, openpyxl, pytest.

**Workspace note:** The thesis evidence tree is currently untracked inside a heavily dirty parent repository, so a Git worktree would omit the required data. This plan executes in place and writes only to the new validation package plus this plan file.

---

### Task 1: Lock the SEM identities and optical orientation

**Files:**
- Create: `Final_Data_Figures/20260712_sem_anchored_center9_validation/scripts/center9_core.py`
- Create: `Final_Data_Figures/20260712_sem_anchored_center9_validation/tests/test_sem_mapping.py`

- [ ] Write a failing test asserting that the physical center-nine cells are `J8:L10` and flattened SEM indices are `22,23,24,28,29,30,34,35,36`.
- [ ] Write a failing test for the complete map: `J8->24->(4,6)`, `K8->23->(4,5)`, `L8->22->(4,4)`, continuing through `J10->36->(6,6)`, `K10->35->(6,5)`, and `L10->34->(6,4)`.
- [ ] Prove the 2026-06-18 capture transform from the four sample quadrants and line directions. Compare all eight rotation/reflection transforms and require a unique geometry match; never select orientation by SEM-error agreement.
- [ ] Run `python -m pytest Final_Data_Figures/20260712_sem_anchored_center9_validation/tests/test_sem_mapping.py -q` and confirm the missing implementation fails.
- [ ] Implement workbook parsing and explicit orientation transforms.
- [ ] Re-run the test and confirm it passes.

### Task 2: Recompute center-nine CD and figures

**Files:**
- Create: `Final_Data_Figures/20260712_sem_anchored_center9_validation/scripts/run_center9_cd.py`
- Create: `Final_Data_Figures/20260712_sem_anchored_center9_validation/tests/test_center9_cd.py`
- Create outputs under: `Final_Data_Figures/20260712_sem_anchored_center9_validation/cd/`

- [ ] Write failing tests for nine unique identities, correct SEM values, and identical Raw/V42 optical centers.
- [ ] Reuse the fixed optical-grid measurements, replace the incorrect direct-column SEM pairing with the mirrored pairing, and retain only Raw and V42 epoch 120.
- [ ] Export the per-pillar table, summary table, 3x3 absolute-error maps, per-pillar SEM/Raw/V42 comparison, and a labeled Raw-image overlay.
- [ ] Retain SEM cell, flattened index, optical row/column, fixed image coordinates, capture transform, and source image in every output row.
- [ ] Verify that every plotted value can be traced to one CSV row and one SEM workbook cell.

### Task 3: Implement nine-pillar local displacement consensus

**Files:**
- Create: `Final_Data_Figures/20260712_sem_anchored_center9_validation/scripts/pillar_motion_core.py`
- Create: `Final_Data_Figures/20260712_sem_anchored_center9_validation/tests/test_pillar_motion_core.py`

- [ ] Write synthetic tests using a 3x3 circular grid shifted by known subpixel amounts.
- [ ] Extend synthetic tests to 50/51-frame sequences with realistic pitch, blur, noise, accumulated motion, and deliberate one-pitch distractors.
- [ ] Assert that repeated structure does not cause a one-pitch mismatch: initialize identities in frame 0, propagate one shared set of predicted windows, keep every search below half a grid pitch, and enforce one-to-one assignment.
- [ ] Detect left and right pillar boundaries on multiple horizontal chords, use their midpoint as each pillar center, and combine nine displacements by a robust median.
- [ ] Report per-pillar residuals from common motion as `within-grid disagreement`; do not call them localization error without independent motion truth.
- [ ] Use the nominal command only to set the search neighborhood; do not fit a scale or offset to the result.

### Task 4: Lock the physical-center corner in each magnification

**Files:**
- Create: `Final_Data_Figures/20260712_sem_anchored_center9_validation/config/sequence_center9.json`
- Create: `Final_Data_Figures/20260712_sem_anchored_center9_validation/scripts/run_center9_displacement.py`
- Create outputs under: `Final_Data_Figures/20260712_sem_anchored_center9_validation/displacement/`

- [ ] Determine the pillar quadrant and inner sample-center corner independently from the first Raw frame of each sequence.
- [ ] Before reading V42 results, store orientation, signed direction, frame count, expected filenames, initial nine identities, pitch, search limit, minimum valid pillars, and rejection rules in the config.
- [ ] Propagate the same physical identities across every frame rather than fixing screen coordinates; never search for a better ROI per case or per step.
- [ ] Apply the same frame pairs, predicted identity windows, and gates to Raw and V42 for all six 50x/20x/5x sequences.
- [ ] Use every consecutive pair as the primary result; compare cases only on common valid identities and report every rejection without substituting steps or regions.
- [ ] Export full-step per-pillar measurements, per-step consensus, summary metrics, and full-frame/crop overlays.
- [ ] Validate each magnification using known subpixel shifts applied to real crops. Mark a sequence unavailable rather than substituting another structure if identities are not traceable or if the resolution-specific recovery test fails, especially at 5x.

### Task 5: Validate and package the thesis evidence

**Files:**
- Create: `Final_Data_Figures/20260712_sem_anchored_center9_validation/REPORT.md`
- Create: `Final_Data_Figures/20260712_sem_anchored_center9_validation/manifest.json`

- [ ] Run the complete pytest suite for the package.
- [ ] Run both CD and displacement entrypoints from a clean process.
- [ ] Recompute headline values independently from exported CSV files.
- [ ] Inspect every final figure at full resolution for incorrect identities, clipping, or misleading scales.
- [ ] Record source paths, orientation transforms, exclusions, units, and limitations in the manifest and report.
- [ ] State that SEM supplies identity and diameter truth, not stage-position truth. Without independent stage readback, limit real-sequence claims to repeatability, commanded-step agreement, and Raw/V42 comparison rather than absolute displacement accuracy.
