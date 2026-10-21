# V42 ROI Sensitivity Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recalculate the six displacement datasets with three traceable ROIs and show exactly how every measurement region and local edge was selected.

**Architecture:** Keep the established frozen-V41 shared-edge displacement core unchanged. Add one audit runner that defines three ROIs per magnification, applies identical frame pairs and ROIs to Raw/V41/V42, exports image overlays and edge diagnostics, and summarizes how conclusions change with ROI choice.

**Tech Stack:** Python 3.12, pandas, NumPy, Pillow, Matplotlib, existing `local_edge_band_core.py`, pytest.

---

### Task 1: Lock ROI and step-selection rules

**Files:**
- Create: `Final_Data_Figures/20260710_v42_full_validation/tests/test_v42_roi_sensitivity.py`
- Create: `Final_Data_Figures/20260710_v42_full_validation/scripts/run_v42_roi_sensitivity.py`

- [ ] Write failing tests requiring three named, in-bounds ROIs per dataset group.
- [ ] Require each selected step to contain Raw, V41, and V42 exactly once.
- [ ] Implement the ROI catalog and symmetric-step filter.
- [ ] Run the tests and confirm they pass.

### Task 2: Export visual audit images

**Files:**
- Modify: `Final_Data_Figures/20260710_v42_full_validation/scripts/run_v42_roi_sensitivity.py`
- Create: `Final_Data_Figures/20260710_v42_full_validation/roi_sensitivity_revalidation/visual_audit/*`

- [ ] Draw all three ROI rectangles on the full Raw and V42 reference images.
- [ ] Export individual Raw/V41/V42 crops for every ROI.
- [ ] Draw the exact frozen-V41 shared edge centers used by the detector.
- [ ] Export representative reference/moving-frame diagnostics and motion arrows.

### Task 3: Recalculate displacement for every ROI

**Files:**
- Modify: `Final_Data_Figures/20260710_v42_full_validation/scripts/run_v42_roi_sensitivity.py`
- Create: `Final_Data_Figures/20260710_v42_full_validation/roi_sensitivity_revalidation/tables/*`

- [ ] Measure all available adjacent steps with each ROI.
- [ ] Apply the existing common-best-30 keys unchanged to all three cases.
- [ ] Save per-step measurements, validity fields, edge counts, ambiguity, localization uncertainty, and total uncertainty.
- [ ] Verify row counts and case symmetry.

### Task 4: Build sensitivity conclusions

**Files:**
- Modify: `Final_Data_Figures/20260710_v42_full_validation/scripts/run_v42_roi_sensitivity.py`
- Create: `Final_Data_Figures/20260710_v42_full_validation/roi_sensitivity_revalidation/REPORT.md`

- [ ] Plot per-step traces for Raw/V41/V42 for every ROI.
- [ ] Plot a dataset-by-ROI improvement matrix and exact-value comparison table.
- [ ] Flag sign reversals, invalid measurements, and high spread across ROIs.
- [ ] State whether each dataset conclusion is robust, ROI-sensitive, or failed.

### Task 5: Final verification

- [ ] Run all ROI and local-edge tests.
- [ ] Recompute headline values independently from per-step rows.
- [ ] Open representative overlay, crop, edge, trace, and matrix images.
- [ ] Confirm no labels overlap and all images use the intended source paths.
