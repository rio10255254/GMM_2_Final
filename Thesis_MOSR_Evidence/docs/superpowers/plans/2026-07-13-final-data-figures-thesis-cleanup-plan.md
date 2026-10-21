# Final Data Figures Thesis Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the scattered `Final_Data_Figures` tree with one current V42 center-nine result package, one minimal V42 epoch-120 source package, one PSF package, and a verified external archive of every superseded original file.

**Architecture:** A tested organizer first inventories every original file and maps it to exactly one retained or archive destination. It uses copy, size/SHA-256 verification, and source removal only after verification. The current result package is then regenerated from cleaned four-sequence configuration and retained sources, so no superseded report or 5x result survives in the formal reading path.

**Tech Stack:** Python 3.12, pathlib/shutil/hashlib/csv/json, pytest, existing NumPy/Pandas/OpenCV/Matplotlib analysis scripts.

---

### Task 1: Build and Test the Safe Organizer

**Files:**
- Create: `Tools/organize_final_data_figures_for_thesis.py`
- Create: `tests/test_organize_final_data_figures_for_thesis.py`

- [ ] Write tests using a temporary miniature folder tree for destination-exists refusal, no-overwrite behavior, copy-before-remove, SHA-256 verification, full original-file reconciliation, and separate recording of newly generated files.
- [ ] Run the focused tests and confirm they fail before implementation.
- [ ] Implement inventory, classification, verified copy/remove, archive manifest, and reconciliation report.
- [ ] Run focused tests and confirm they pass.
- [ ] Run the organizer in dry-run mode against the real tree and inspect the proposed retained/archive counts and bytes.

### Task 2: Capture the Pre-Move Evidence State

**Files:**
- Create: `docs/final_data_figures_cleanup/pre_move_inventory_20260713.csv`
- Create: `docs/final_data_figures_cleanup/pre_move_summary_20260713.json`

- [ ] Inventory every original file with relative path, byte size, modified time, and SHA-256.
- [ ] Verify the existing Raw eligibility lock.
- [ ] Recreate and verify the existing 87-file protected-evidence content set before any move.
- [ ] Record the 72-test baseline and four current candidate rows.

### Task 3: Move Original Files Without Data Loss

**Files:**
- Create directory: `Archive/Final_Data_Figures_Superseded_20260713/`
- Create directory: `Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/`
- Create directory: `Final_Data_Figures/02_V42_E120_SOURCE_MATERIAL/`
- Move directory: `Final_Data_Figures/PSF_Experiment_Results_Analysis/` to `Final_Data_Figures/03_PSF_EXPERIMENT_RESULTS/`

- [ ] Confirm all resolved source/destination paths stay within `Thesis_MOSR_Evidence` and the archive destination is absent.
- [ ] Move all obsolete top-level V41, V41.1, old detector, checkpoint, and audit folders into the archive using copy/verify/remove.
- [ ] Archive the original `20260712_sem_anchored_center9_validation` package unchanged.
- [ ] Split `20260710_v42_full_validation`: retain only static/50x/20x epoch-120 reconstructions, their five inference logs, and required CD source table in the source-material folder; archive every other original file, including 5x, circle, synthetic, old ROI, and old report material.
- [ ] Reconcile every original file against retained plus archive destinations.

### Task 4: Generate the Clean Current Result Package

**Files:**
- Create: `Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/config/sequence_center9_50x20x.json`
- Create: `Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/scripts/*.py`
- Create: `Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/tests/*.py`
- Create: `Final_Data_Figures/02_V42_E120_SOURCE_MATERIAL/source_manifest.json`

- [ ] Copy the necessary center-nine CD and unified-audit scripts from the archived originals as new cleaned files.
- [ ] Update the CD and V42 source paths to the new source-material folder.
- [ ] Create a four-sequence-only configuration with pillar IDs 22, 23, 24, 28, 29, 30, 34, 35, and 36.
- [ ] Update the audit defaults to the new four-sequence configuration and current output folders.
- [ ] Keep exact canonical Raw/mapping/edge-phase/SEM/weight paths in the source register, including the canonical parent name `20260704_20x_5x_analysis` without treating it as a 5x result.
- [ ] Run the focused tests for CD, SEM identity, and unified displacement audit.

### Task 5: Regenerate CD and Displacement Results

**Files:**
- Generate: `Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/cd/`
- Generate: `Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/diagnostics/unified_displacement_step_audit/`
- Generate: `Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/thesis_50x_20x/displacement_screened_candidate/`

- [ ] Run the center-nine CD pipeline from the retained CD source, static Raw image, static V42 image, and SEM workbook.
- [ ] Run the four-sequence Raw-locked/V42-blind displacement audit from retained 50x/20x reconstructions and canonical Raw/mapping sources.
- [ ] Independently recompute every headline value from the newly generated detailed tables.
- [ ] Verify the Raw lock hash and 20/25/30% direction stability.
- [ ] Open and inspect every formal figure.

### Task 6: Create the Thesis Reading Path

**Files:**
- Create: `Final_Data_Figures/README_CURRENT_THESIS_RESULTS.md`
- Create: `Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/README.md`
- Create: `Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/SOURCE_REGISTER.csv`
- Create: `Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/PACKAGE_INVENTORY_SHA256.csv`
- Create: `Archive/Final_Data_Figures_Superseded_20260713/ARCHIVE_MANIFEST.csv`
- Create: `Archive/Final_Data_Figures_Superseded_20260713/README.md`

- [ ] Write the thesis entry in the order PSF characterization, V42 role, center-nine CD, 50x/20x displacement, limitations.
- [ ] State the four screened results and place the full-unfiltered 20x 0.5 um caveat beside them.
- [ ] State that PSF fitting is independent optical-system evidence; do not claim the fitted experimental PSF caused V42 results.
- [ ] Explain each folder by its thesis role rather than only listing paths.
- [ ] Generate current-package and archive fingerprints.

### Task 7: Final Verification

**Files:**
- Create: `docs/final_data_figures_cleanup/post_move_verification_20260713.md`

- [ ] Confirm the formal root contains exactly the README plus the three chapter-aligned folders.
- [ ] Confirm no formal filename, sequence entry, table row, figure, or claim contains a 5x result; allow only exact provenance parent paths.
- [ ] Scan readable formal files for superseded V41/checkpoint claims and old headline values.
- [ ] Verify every retained link and source path resolves.
- [ ] Run the full cleaned test suite.
- [ ] Reconcile all original files and all newly generated files.
- [ ] Record final folder counts, sizes, hashes, headline values, tests, and caveats in the verification report.
