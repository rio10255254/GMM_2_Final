# R60 Full-Power R58/R59 Operation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a full-power first formal branch using the best current R58 setting, then apply R59 CD-closed-loop correction and independently measure the final CD.

**Architecture:** Reuse the existing R58 data/training/reconstruction automation and the existing R59 CD correction layer. Use a separate full-run data root so pilot data is preserved; train the `r58_frac050` branch with more anchors and longer exposure, then validate pre/post R59 on the same SEM/CD measurement template.

**Tech Stack:** Python, PyTorch/CUDA, OpenCV, existing R58/R59/R57 scripts, pytest.

---

### Task 1: Pre-Run Verification

**Files:**
- Existing R58 automation scripts
- Existing R59 calibration script

- [ ] **Step 1: Run R58 and R59 unit tests**

Run:
`C:\Users\Rio\anaconda3\python.exe -m pytest LabSystem_MOSR\Experiments\R58_MeasurementClosedLoopMOSR\tests LabSystem_MOSR\Experiments\R59_CDClosedLoopBoundaryLayer\tests -q`

Expected: all tests pass.

### Task 2: Full-Power R58 Training Branch

**Files:**
- Output data root: `LabSystem_MOSR/Training_Data/r60_full_power/hs100mg_basler`
- Output reports: `LabSystem_MOSR/Experiments/R58_MeasurementClosedLoopMOSR/reports/r58_automated_rounds`

- [ ] **Step 1: Generate full anchor package**

Use `r58_frac050_train` profile with 4096 anchor pairs, no pilot data overwrite.

- [ ] **Step 2: Train `r58_frac050` full branch**

Run 30 epochs with up to 512 training batches per epoch, CUDA, batch size 4.

- [ ] **Step 3: Reconstruct and measure**

Use the same 100MG image and the same SEM/CD measurement template.

### Task 3: R59 Final CD Lock

**Files:**
- Output reports: `LabSystem_MOSR/Experiments/R59_CDClosedLoopBoundaryLayer/reports/r59_cd_closed_loop`

- [ ] **Step 1: Apply R59 to the full R58 reconstruction**

Fit the CD correction on the full R58 output and write corrected image.

- [ ] **Step 2: Independently re-measure corrected image**

Use the older R57 measurement script as an independent check.

### Task 4: Final Report

- [ ] **Step 1: Compare baselines**

Report original image, best R58 pilot, R58 full branch, and R59 corrected full branch.

- [ ] **Step 2: Call out limits**

State whether this is same-sample calibrated evidence or full generalization evidence.
