# R59 CD Closed-Loop Boundary Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fast R59 measurement-calibrated boundary layer that learns SEM-driven circle-edge shifts from the current reconstruction, applies them to the 100MG image, and verifies the corrected CD against the same SEM measurement gate.

**Architecture:** R59 is a post-reconstruction calibration layer, not a full model retrain. It imports the verified R57 CD template measurement functions, fits one robust radius shift per feature class (`圓孔`, `圓柱`), applies a local radial edge warp around each template circle, writes the corrected image and model JSON, and re-runs CD measurement.

**Tech Stack:** Python, OpenCV, NumPy, existing R57 CD measurement script, pytest.

---

### Task 1: R59 Unit Tests

**Files:**
- Create: `LabSystem_MOSR/Experiments/R59_CDClosedLoopBoundaryLayer/tests/test_r59_cd_boundary_layer.py`

- [ ] **Step 1: Write failing tests**

Test these behaviors:
- Fitting class shifts from measured-vs-SEM rows returns the expected pixel shift.
- Applying a positive shift to a dark circle increases the measured radius.
- Applying a negative shift to a bright circle decreases the measured radius.
- The end-to-end helper writes a corrected image and a calibration JSON.

- [ ] **Step 2: Run test to verify it fails**

Run:
`C:\Users\Rio\anaconda3\python.exe -m pytest "Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R59_CDClosedLoopBoundaryLayer/tests" -q`

Expected: FAIL because R59 scripts do not exist.

### Task 2: R59 Calibration Layer

**Files:**
- Create: `LabSystem_MOSR/Experiments/R59_CDClosedLoopBoundaryLayer/scripts/run_r59_cd_closed_loop.py`

- [ ] **Step 1: Implement fitting helpers**

Add helpers to read template rows, estimate per-circle radius using R57 code, compute class-level robust shifts in pixels, and write a small calibration model JSON.

- [ ] **Step 2: Implement radial boundary warp**

For each template circle, locally remap pixels in a narrow annulus so the measured edge shifts by the fitted class correction. Use feathered blending so areas away from the edge are unchanged.

- [ ] **Step 3: Implement CLI automation**

CLI should accept an input reconstruction image, output directory, candidate label, and measurement paths. It should write:
- corrected BMP
- pre/post CD summaries
- calibration JSON
- status report JSON/MD

### Task 3: Verification and Real Run

**Files:**
- Output: `LabSystem_MOSR/Experiments/R59_CDClosedLoopBoundaryLayer/reports/...`

- [ ] **Step 1: Run unit tests**

Expected: all R59 tests pass.

- [ ] **Step 2: Run R59 on the best R58 reconstruction**

Use the best measured R58 output from the `0.50`, 8-epoch pilot as input.

- [ ] **Step 3: Re-measure corrected image**

Use the same R57 CD measurement template. Success is not visual sharpness; success is lower mean absolute radius error versus SEM.

- [ ] **Step 4: Compare against known baselines**

Report:
- original image mean error: 38.59 nm
- best R58 long-pilot mean error: 54.91 nm
- R59 corrected mean error
