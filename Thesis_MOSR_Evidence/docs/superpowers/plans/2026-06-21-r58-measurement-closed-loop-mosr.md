# R58 Measurement-Closed-Loop MOSR Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run an R58 LabSystem_MOSR experiment that strengthens 100MG/Basler boundary reconstruction with real-style anchor data and CD-gated checkpoint selection.

**Architecture:** Add a new `R58_MeasurementClosedLoopMOSR` experiment package beside R57. Reuse R57's verified CD measurement/gate tools, but generate softer real-style 100MG anchors, launch several short fine-tune variants from the R55 best checkpoint, reconstruct the same 100MG source image for every checkpoint, measure CD, and rank candidates by SEM-referenced radius error plus non-regression gates.

**Tech Stack:** Python, OpenCV, NumPy, PyTorch training entrypoint from `D:\GMM_2_Final\Model`, existing LabSystem_MOSR reconstruction and R57 CD measurement utilities.

---

### Task 1: R58 Data Package Builder

**Files:**
- Create: `LabSystem_MOSR/Experiments/R58_MeasurementClosedLoopMOSR/scripts/prepare_r58_measurement_dataset.py`
- Test: `LabSystem_MOSR/Experiments/R58_MeasurementClosedLoopMOSR/tests/test_prepare_r58_measurement_dataset.py`
- Docs: `LabSystem_MOSR/Experiments/R58_MeasurementClosedLoopMOSR/MANIFEST.md`

- [ ] Step 1: Write tests for weak CD correction schedules, shared circle layout, real-style source gradients, and manifest counts.
- [ ] Step 2: Run the new data-builder tests and confirm they fail because the script does not exist.
- [ ] Step 3: Implement the data builder by reusing R57's geometry-sidecar pattern but replacing full-radius correction with fractional correction profiles.
- [ ] Step 4: Generate a small smoke dataset and verify source/label centers match while radius deltas follow the intended fractions.
- [ ] Step 5: Generate the full R58 training package.

### Task 2: R58 Launcher

**Files:**
- Create: `LabSystem_MOSR/Experiments/R58_MeasurementClosedLoopMOSR/scripts/launch_r58.py`
- Test: `LabSystem_MOSR/Experiments/R58_MeasurementClosedLoopMOSR/tests/test_launch_r58.py`

- [ ] Step 1: Write tests that confirm candidate profiles map to the right data package, use R55 best checkpoint by default, disable PSF-forward loss, and enable boundary geometry from epoch 0 or 1.
- [ ] Step 2: Run launcher tests and confirm they fail because the script does not exist.
- [ ] Step 3: Implement launcher profiles for `r58_frac025`, `r58_frac050`, and `r58_frac075`.
- [ ] Step 4: Dry-run all candidate profiles and verify JSON summaries contain data, checkpoint, boundary, PSF, and training settings.

### Task 3: R58 Automated Training and CD Evaluation

**Files:**
- Create: `LabSystem_MOSR/Experiments/R58_MeasurementClosedLoopMOSR/scripts/run_r58_automated_rounds.py`
- Test: `LabSystem_MOSR/Experiments/R58_MeasurementClosedLoopMOSR/tests/test_run_r58_automated_rounds.py`

- [ ] Step 1: Write tests for command construction, checkpoint discovery, reconstruction output discovery, CD measurement invocation, and ranking logic.
- [ ] Step 2: Run automation tests and confirm they fail because the script does not exist.
- [ ] Step 3: Implement the automation runner with `--dry-run`, `--train`, `--reconstruct`, `--measure`, and `--rank-only` modes.
- [ ] Step 4: Dry-run the full three-candidate workflow.
- [ ] Step 5: Execute short multi-round training with conservative limits, then reconstruct and measure each candidate.

### Task 4: Verification and Report

**Files:**
- Create/update: `LabSystem_MOSR/Experiments/R58_MeasurementClosedLoopMOSR/reports/R58_AUTOMATED_ROUNDS_STATUS.md`
- Create/update: `LabSystem_MOSR/Experiments/R58_MeasurementClosedLoopMOSR/reports/r58_automated_results.json`

- [ ] Step 1: Run all R58 tests.
- [ ] Step 2: Run R58 dry-runs.
- [ ] Step 3: Run short training/reconstruction/CD measurement if compute is available.
- [ ] Step 4: Compare R58 candidates against original image, R55, R57, and R57.1.
- [ ] Step 5: Mark the best candidate as exploratory only unless it beats the original image on required CD gates.
