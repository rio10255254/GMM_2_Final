# Final Data Figures Thesis Cleanup Design

## Goal

Reorganize `Final_Data_Figures` so its main reading path supports one current thesis story, while superseded and contradictory results remain traceable outside the formal results area.

## Thesis Story

The formal result path must follow the order in which the thesis argues its case:

1. PSF fitting and validation establish the optical characterization of the experimental system and demonstrate the project's PSF-handling capability. They are not presented as the proven cause of the final V42 result because the fitted experimental PSF has not been matched to the checkpoint-buffer PSF used by this inference run.
2. V42 epoch 120 is the single thesis model used for the final comparisons.
3. The center nine SEM-identified pillars provide the common physical measurement target.
4. For this static capture and these nine pillars, CD validation shows that all nine V42 measurements move closer to SEM than Raw, while retaining the absolute-error caveat.
5. Displacement validation uses the same nine pillars at 50x and 20x only. The primary population is locked from Raw timing and platform-consistency checks before V42 is compared.
6. The conclusion is that the Raw-screened subsets of these four captured sequences have lower measured variation and lower local nine-pillar disagreement after V42. It is not proof that the model makes the physical stage more stable or proves absolute displacement accuracy.

## Formal Folder Structure

`Final_Data_Figures` will contain only these three top-level result lines plus one entry document:

- `01_CURRENT_THESIS_RESULTS_V42_CENTER9`
  - Current CD tables and figures for the SEM-known center nine pillars.
  - Current 50x and 20x displacement candidate tables, figures, detailed Raw-locked/V42-blind audit, scripts, tests, and reproducibility records.
  - The screened-candidate readout and unified Raw-blind audit are the only formal displacement result.
  - The older `THESIS_REPORT.md`, old `figures/`, old `tables/`, old six-sequence `displacement/`, and earlier diagnostic summaries are archived because they report different populations or include 5x.
- `02_V42_E120_SOURCE_MATERIAL`
  - Only source material needed to reproduce the current CD and displacement results: static 100MG, 50x 0.5/1 um, and 20x 0.5/1 um V42 reconstructions, the CD source table/manifest, and necessary inference traceability.
  - Old reports, checkpoint sweeps, synthetic/generalization side tests, concentric-circle side tests, 5x reconstructions, and superseded ROI analyses leave the formal area.
  - Retained source logs must show the exact epoch-120 weight, checkpoint-buffer PSF source, physics status, input count, and output location used for each formal reconstruction.
- `03_PSF_EXPERIMENT_RESULTS`
  - The existing PSF fitting, sensitivity, and repeatability evidence, preserved as an independent Chapter 6 evidence line.
- `README_CURRENT_THESIS_RESULTS.md`
  - The only starting point for a thesis reader. It states what to use, what each folder proves, the headline values, limitations, and where historical work was archived.

## Archive Structure

Superseded material will be moved, not permanently deleted, to:

`Thesis_MOSR_Evidence/Archive/Final_Data_Figures_Superseded_20260713`

The archive will contain:

- Old V41 visual/CD package.
- V41 standalone validation.
- Old uncertainty-aware displacement readout.
- V41.1 quick fine-tune validation.
- V41 label/SNR audit.
- V42 intermediate-checkpoint CD and displacement packages.
- Superseded parts of the V42 full-validation package.
- Superseded six-sequence/5x parts and old thesis summaries from the center-nine package.
- A manifest recording every moved path, reason, size, and destination.

The exact retained displacement result is:

- `diagnostics/unified_displacement_step_audit/`
- `thesis_50x_20x/displacement_screened_candidate/`
- `scripts/audit_all_displacement_sequences.py`
- `scripts/displacement_audit_core.py`
- `scripts/pillar_motion_core.py`
- `tests/test_unified_displacement_audit.py`
- A new four-sequence-only `config/sequence_center9_50x20x.json` containing only 50x 0.5/1 um and 20x 0.5/1 um.

The original six-sequence `config/sequence_center9.json` and the original audit script are archived unchanged. The retained audit script is a cleaned generated copy that defaults to the new four-sequence configuration. Any other changed original script, test, report, or configuration is likewise archived unchanged before a cleaned copy is generated.

The older four-sequence `THESIS_REPORT.md`, `thesis_50x_20x/figures/`, and `thesis_50x_20x/tables/` are archived even though they omit 5x, because they use a different unscreened/session-correction population and contain different headline values.

## Current Headline Results

The formal entry document will report:

- Center-nine CD for this static capture: Raw mean absolute error 92.99 nm; V42 78.18 nm; all nine measured pillars improve; absolute bias remains.
- 50x 0.5 um: 48/50 Raw-screened, platform-consistent steps; SD 8.15 to 6.15 nm; 24.55% reduction; nine-pillar disagreement 12.86 to 4.12 nm.
- 50x 1 um: 48/49 Raw-screened, platform-consistent steps; SD 11.08 to 7.96 nm; 28.15% reduction; disagreement 12.13 to 4.09 nm.
- 20x 0.5 um: 46/49 Raw-screened, platform-consistent steps; SD 22.33 to 20.71 nm; 7.24% reduction; disagreement 21.25 to 12.41 nm.
- 20x 1 um: 49/49 Raw-screened, platform-consistent steps; SD 27.03 to 25.38 nm; 6.09% reduction; disagreement 18.99 to 12.34 nm.

The entry document must disclose beside the screened result that the full unfiltered 20x 0.5 um sequence is slightly worse after reconstruction, and that the positive candidate result depends on excluding three Raw-confirmed incomplete/cross-axis platform motions under a rule locked before V42 was compared.

## Complete Source Register

The current result package will contain a source register with path, role, byte size, and SHA-256 for:

- The 50x and 20x Raw image sequences and their capture-time/input-mapping files.
- The 20x edge/phase reference table used as the predeclared supplemental diagnostic input.
- The retained V42 epoch-120 static, 50x, and 20x reconstructions.
- The 100MG static Raw image and SEM workbook.
- The V42 epoch-120 weight and model-package record.
- The CD source table and CD validation manifest.
- The Raw eligibility lock file and its recorded SHA-256.
- The unified audit scripts, configuration, tests, output tables, and figures.
- The retained inference logs for static, 50x, and 20x reconstruction.

External Raw, SEM, and weight sources may remain in their canonical project locations, but every one must be registered, present, and fingerprinted. The retained V42 reconstructions and logs will live in `02_V42_E120_SOURCE_MATERIAL`.

## Path and Reproducibility Rules

- All moved source paths referenced by retained metadata/configuration/scripts must be updated, and every readable retained reference must resolve.
- The current package must identify pillar IDs 22, 23, 24, 28, 29, 30, 34, 35, and 36.
- The formal displacement package must contain exactly four sequence entries and no 5x result, figure, table row, or claim. Exact provenance paths may contain a parent folder named `20260704_20x_5x_analysis`; that text does not constitute a retained 5x sequence or result.
- The existing Raw eligibility lock hash must remain verifiable.
- Before moving, the old protected evidence set and its path-dependent digest must be verified against the current tree. Because paths change during reorganization, each old protected file's content fingerprint must then be preserved and reconciled across retained plus archived destinations rather than requiring the old path-dependent digest to reproduce inside the cleaned folder.
- The cleaned formal package receives a new independent inventory and SHA-256 digest after reorganization.
- Existing historical evidence may change location but must not change file content.
- The archive destination must not exist before execution, and no destination file may be overwritten.
- The organizer must inventory the full original `Final_Data_Figures` tree, copy each archive-bound file, verify size and SHA-256, then remove only the verified source file. If verification fails, the source remains in place.
- A post-move reconciliation must prove that every original file appears exactly once in either the retained tree or archive with matching size and SHA-256. Newly generated cleaned files are listed separately and are excluded from the original-file reconciliation totals.

## Verification

Completion requires:

1. All retained scripts and tests pass after path updates.
2. Current CD and displacement headline values are recreated by a fresh run from the registered source images, not merely copied or recomputed from summary tables.
3. All current figures open correctly, and all links/source references in the final entry document resolve.
4. The formal root contains only the three chapter-aligned folders and the current-results entry document.
5. No readable formal file contains superseded headline values or claims universal displacement superiority, absolute stage truth, or a 5x result/improvement. Exact source paths containing the canonical parent-folder name `20260704_20x_5x_analysis` are allowed.
6. The Raw selection-lock SHA-256 still matches. The old protected set is verified before moving, every old protected file keeps the same content fingerprint after moving, and a new cleaned-package inventory/digest is generated.
7. The full-unfiltered 20x 0.5 um caveat appears beside the screened result wherever it is summarized.
8. Every archived file is listed and hash-verified at its destination, and the original inventory reconciles exactly across retained plus archived files.
