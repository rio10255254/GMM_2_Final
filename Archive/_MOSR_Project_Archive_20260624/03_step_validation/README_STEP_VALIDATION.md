# Step Validation Curated Evidence 20260624

Purpose: keep the Step sample evidence readable and separate from exploratory working files.

Main conclusions:
- Scale used for Step: 2.5 um camera pixel / 20x objective = 0.125 um/px.
- Raw full image circle measurements over 40 frames: 100 um -> 99.321 um, 200 um -> 199.553 um, 300 um -> 299.736 um, 500 um -> 499.905 um.
- Center crop raw vs reconstruction over 40 frames: raw 100/200 um -> 99.288/199.519 um; v16 -> 99.462/199.692 um.
- Reconstruction slightly improves CD closeness on the measured 100/200 um circles without breaking displacement validation.
- Roundness comparison is only approximate from optical image fitting, not the same instrument method as Mitutoyo.

Folder map:
- 01_selection: selected Step frames and pair tables.
- 02_gmf_validation: copied package metadata and external GMF score analysis summaries.
- 03_cd_shape_validation: CD/shape tables and overlays from the report-photo check.
- 04_figures: compact previews for visual review.
- 05_source_references: source path notes.

The original GMF/reconstruction packages remain in the Step analysis folder because some package files contain absolute paths.
