# R57.1 Asymmetric CD Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify an R57.1 training path that explicitly teaches the model to expand via boundaries and shrink pillar boundaries on the HS-100MG / Basler sample.

**Architecture:** Keep the R57 model architecture and training core. Change the generated HS-100MG anchor data so the input image has the measured raw CD bias while the label keeps the SEM target size, then train with anchor-focus and select checkpoints by the SEM-referenced CD gate.

**Tech Stack:** Python, OpenCV, NumPy, PyTorch trainer entry `GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py`, existing LabSystem_MOSR reconstruction and CD measurement scripts.

---

### Task 1: Add Asymmetric Anchor Data Behavior

**Files:**
- Modify: `Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R57_GeometryConstrainedMOSR/scripts/prepare_r57_geometry_dataset.py`
- Test: `Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R57_GeometryConstrainedMOSR/tests/test_prepare_r57_geometry_dataset.py`

- [x] **Step 1: Write failing test**

Add a test that generated anchor records include different source and target radii:

```python
assert via_record["source_radius_nm"] < via_record["target_radius_nm"]
assert pillar_record["source_radius_nm"] > pillar_record["target_radius_nm"]
```

- [x] **Step 2: Run test and verify it fails**

Run:

```powershell
C:\Users\Rio\anaconda3\python.exe -m pytest Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R57_GeometryConstrainedMOSR/tests/test_prepare_r57_geometry_dataset.py -q
```

Expected: fail because anchor records do not yet expose source/target radius bias.

- [x] **Step 3: Implement asymmetric source generation**

Generate labels at SEM radius, but generate source images from feature-specific raw-like radius:

```python
source_radius_nm = SEM_RADIUS_NM[feature] + SOURCE_RADIUS_BIAS_NM[feature]
target_radius_nm = SEM_RADIUS_NM[feature]
```

Default bias:

```python
SOURCE_RADIUS_BIAS_NM = {
    "via": -66.13489918240407,
    "pillar": 11.043151807599543,
}
```

- [x] **Step 4: Run test and verify it passes**

Run the same test file.

### Task 2: Add R57.1 Launcher Identity

**Files:**
- Modify: `Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R57_GeometryConstrainedMOSR/scripts/launch_r57.py`
- Test: `Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R57_GeometryConstrainedMOSR/tests/test_launch_r57.py`

- [x] **Step 1: Write failing test**

Add a launcher test for candidate `r57_1_asym_cd_anchor_finetune` and verify:

```python
assert Trainer.CFG.R57_ASYMMETRIC_CD_CORRECTION is True
assert Trainer.CFG.TRAIN_INCLUDE_SUBDIRS == ("stage_34_hs100mg_anchor",)
```

- [x] **Step 2: Run test and verify it fails**

Expected: fail because candidate is not registered.

- [x] **Step 3: Implement candidate**

Add candidate mapping and set identity fields. Use anchor-focus by default when this candidate is selected.

- [x] **Step 4: Run launcher tests and verify pass**

Run:

```powershell
C:\Users\Rio\anaconda3\python.exe -m pytest Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R57_GeometryConstrainedMOSR/tests/test_launch_r57.py -q
```

### Task 3: Regenerate Data and Run R57.1 Pilot

**Files:**
- Generated package: `Thesis_MOSR_Evidence/LabSystem_MOSR/Training_Data/r57_geometry_constrained/hs100mg_basler_anchor/r57_hs100mg_r55_finetune_train`
- Training outputs under `Thesis_MOSR_Evidence/LabSystem_MOSR/Traing_Progress`

- [x] **Step 1: Regenerate dataset**

Run:

```powershell
C:\Users\Rio\anaconda3\python.exe -u Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R57_GeometryConstrainedMOSR/scripts/prepare_r57_geometry_dataset.py
```

- [x] **Step 2: Dry-run launcher**

Run:

```powershell
C:\Users\Rio\anaconda3\python.exe -u Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R57_GeometryConstrainedMOSR/scripts/launch_r57.py --candidate r57_1_asym_cd_anchor_finetune --num-epoch 4 --batch-size 4 --val-batch-size 2 --num-workers 2 --seq-batch-size 2 --max-train-batches 120 --val-ratio 0.02 --run-suffix asym_cd_anchor_e004_b004_mtb120_lr3e6 --device cuda:0 --lr 3e-6 --dry-run
```

- [x] **Step 3: Run pilot training**

Run the same command without `--dry-run`.

### Task 4: Reconstruct and Gate R57.1

**Files:**
- Reconstruct output under `LabSystem_MOSR\Reconstruct_Progress\20260618_100MG_user_recon`
- CD output under `LabSystem_MOSR\Reconstruct_Progress\20260618_100MG_user_recon`
- Report under `LabSystem_MOSR\Experiments\R57_GeometryConstrainedMOSR\reports`

- [x] **Step 1: Reconstruct current 100MG image with R57.1 latest**

Run inference with weak-PSF disabled and the R57.1 latest checkpoint.

- [x] **Step 2: Measure CD from verified template centers**

Run `measure_r57_cd_from_template.py` on the reconstruction.

- [x] **Step 3: Run CD gate**

Run `validate_r57_cd_gate.py` against original image reference.

- [x] **Step 4: Update report**

Update `R57_PILOT_TRAINING_STATUS.md` with R57.1 results and adoption status.

## Execution Result

Executed on 2026-06-20. R57.1 asymmetric CD aligned pilot completed, but failed
the 100MG CD gate and is rejected. The best current exploratory candidate remains
R57 anchor-focus latest, which is also not adopted because it still does not beat
the original image.
