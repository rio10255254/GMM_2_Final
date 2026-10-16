# Execution and recovery runbook

Scope: preparation is complete only when the handoff checker and its negative
tests pass. This document does NOT certify the next scientific design.

## 1. Commands that exist now

Run from a PowerShell terminal. These commands do not start training:

```powershell
Set-Location -LiteralPath 'D:\GMM_2_Final\Experiments\R118_PhysicalCoordinateRepairScratch'
& 'C:\Users\Rio\anaconda3\python.exe' scripts\next_design.py audit
& 'C:\Users\Rio\anaconda3\python.exe' scripts\next_design.py next
& 'C:\Users\Rio\anaconda3\python.exe' scripts\next_design.py show P02
& 'C:\Users\Rio\anaconda3\python.exe' -m pytest tests\test_next_design_handoff.py -q
```

The helper imports only the Python standard library. Audit hashes protected
inputs, checks existing manifests and dependencies, and reads process state.
It never imports the model, renders confirmation images, or launches a trainer.
Hashing confirmation files is integrity checking, not opening them for model
selection. Its sealed-status check can verify the saved declaration, not prove
that no person or unknown program has ever accessed the set.

An optional `audit --output <new-json-path>` writes one new audit file; it
refuses to overwrite an existing file. Without that flag all commands are
read-only. `next` accepts completed phase receipts only after their required
evidence hashes, checks, dependencies, and plan revision are verified.
These are evidence-integrity checks, NOT an automatic scientific reviewer.

Current source unit tests, also not a training launch:

```powershell
& 'C:\Users\Rio\anaconda3\python.exe' -m pytest tests\test_repairs.py -q
```

Do NOT execute the following as the next-design launch:

- Train.py: runs current R118 readiness and its original 42-epoch formal run.
- training/train.py --mode formal: replaces a supplied epoch/limit with the
  formal configuration; it does not implement the proposed candidate matrix.
- An old R117/R116 validation import in a new process: some modules create
  output folders on import and carry historical method names.

All future W commands MUST first be implemented in P01-P06, tested, and written
to W/reports/commands.json. Do not invent a command merely because this plan
names its intended file. The current handoff helper deliberately cannot train.

## 2. Process and hardware precheck

Use read-only checks before any future GPU work:

```powershell
Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python|matlab' } | Select-Object ProcessId,ParentProcessId,Name,CommandLine
nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu --format=csv
Get-PSDrive -Name D,H | Select-Object Name,Used,Free
```

Identify a process by its exact command, experiment/run ID, executable, and
start time, not by the word python. Only one trainer for this plan may run.
Another experiment's process is never permission to terminate it.

Initial measured R118 settings: batch 12 / workers 4 for full training.
Batch 24 used about twice the memory with effectively unchanged throughput;
do not equate occupied memory with speed. Record measured scenes/s and end-to-end
epoch time, including validation and writes. Do not promise an ETA before a
completed representative epoch. Display both current epoch and whole run ETA,
using recent comparable stage times and separate validation overhead.

The latest user preference is to use resources assertively while keeping the
machine and training usable; the old 9-GiB automation rule is NOT reinstated.
A low-free-memory snapshot alone is not a scientific stop condition.
On a genuine out-of-memory error preserve the attempt, free only this plan's
unused objects, and test a lower microbatch with equal effective batch/step
budget. A matched probe comparison must share the revised execution setting.
Do not change a running process's files, kill unrelated software, or reduce
resolution/coverage silently. If hardware errors repeat, diagnose logs before
restarting; do not loop unattended restarts.

## 3. Receipt and checkpoint protocol

Each implemented phase writes one receipt under
W/reports/handoff_receipts/Pxx.json. P00 is freshly evaluated by the helper
and needs no saved receipt. Use the schema in next_design_plan.json.

Required receipt fields: schema_version=1, plan_id, phase, status=complete,
completed_at_utc, checks (each required check has passed=true and an actual
evidence path), artifacts (relative path + actual SHA-256), and notes.
All paths must remain inside W; protect external inputs through the asset
snapshot, not by putting `../` paths in receipts. `completed_at_utc` is UTC
ISO-8601 with timezone. Copy neither sample hashes nor unrun pass flags.

Only mark a phase complete after running its verification. If a required output
changes, its receipt becomes stale. Retain the old receipt as a historical
attempt, verify the affected phase again, and revalidate dependent phases.
Never mark an invalid matrix cell as a completed zero score.

For a resumed conversation: read NEXT_STEPS, audit, next, then the single
pending phase card. Do not restart all phases just because conversation context
was compacted. The saved receipts are execution evidence, not new instructions.

## 4. Existing locked shape/SEM adapters

The following are REAL R118 commands but are examples for a future requested
R118 reference rerun, not authorization to rerun expensive validation now:

```powershell
& 'C:\Users\Rio\anaconda3\python.exe' validation\locked_acm.py --checkpoint runs\verified_physical_repair\weights\epoch_012.pth --output results\reference_acm_new --method-name R118_E12 --suite R73 R74 --device cuda:0
& 'C:\Users\Rio\anaconda3\python.exe' validation\sem.py --checkpoint runs\verified_physical_repair\weights\epoch_012.pth --output results\reference_sem_new --name R118_E12
```

Use a genuinely new output directory, never overwrite completed results.
For W candidates make a versioned adapter using W's loader. Keep the locked
measurement program, inputs, quantization and calibration unchanged.

ACM source: R114_ConfidenceGatedRecoverableScratch/validation/
run_split_profile_locked_acm.py, with its manifests/R73.json and R74.json.
Each suite contains 100 images. Existing full-suite outputs have 400 primary
method rows, 100 truth rows, and 90 sensitivity rows; validate method identities
and exact keys rather than blindly multiplying this count for new methods.
The runner's historical `sealed_full` label denotes protocol scope: these
reused populations are DEVELOPMENT, not new sealed scientific evidence.

SEM source: R69_ACMContourSEMValidation/scripts/run_acm_extraction.m.
Actual SEM inputs are P-01.tiff through P-09.tiff under
H:/From_2TB_D_disk/13_thesis/SEM_data. Reuse the existing 36-pillar correspondence.
P01..P09 block ordering is (3,1),(3,2),(3,3),(2,3),(2,2),(2,1),(1,1),(1,2),(1,3).
Retain the source script's local corner/global ID mapping; do not reorder based
on reconstruction appearance. Optical exposure inputs are 13.bmp..24.bmp in
R69/inputs/sem_paired_50x_exposure_stack. Existing paired outputs have 864 primary
and 648 sensitivity rows. Report 36 independent pillars and 12 exposures.
Circle initialization does not make the final contour circular ground truth.

The exact absolute source paths and hashes are in next_design_assets.json.

## 5. Real LSC bridge: what must be preserved

Start from R116_CoherentGeometryAnchorScratch/validation/run_lsc_e42.py.
Its current CLI is --method, --recon-root, --output. Do not run it blindly on a
new model: it has defaults/import-time outputs in the old experiment.
Refactor a copy into W with explicit roots, versioned identity and no writes
on import. Run fixture and reference parity checks before any new conclusion.

Required source references (exact paths are in assets):

- R111 results/lsc_current_top30/tables/
  four_method_lsc_per_pair_current_top30.csv: historical comparator population.
- Thesis Final_Data_Figures/04_V42_NEURAL_NETWORK_RESULTS/tables/
  top30_raw_motion_selection.csv: preselected pairs from Raw, never candidate
  output selection.
- Thesis Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/config/
  sequence_center9_50x20x.json: sequence inputs, units, acquisition metadata.
- The same thesis tree's diagnostics/unified_displacement_step_audit/tables/
  raw_eligibility_locked_before_v42.csv and session_anchor_summary.csv.
- R80_InflectionReferenceCircleSEMValidation/scripts/run_displacement_lsc.py
  and its reference_circle_core dependency.

Sequence-to-reconstruction directory mapping:

| Locked sequence ID | Reconstruction subfolder |
|---|---|
| 50x_x_0p5um | 50x_0p5um |
| 50x_x_1um | 50x_1um |
| 20x_0p5um | 20x_0p5um |
| 20x_1um | 20x_1um |

Inventory: 30 fixed pairs per sequence, four sequences, 120 pairs. Their
union contains 159 input frames (43/42/34/40 respectively), nine features per
frame, 1,431 expected center rows. Invalid centers retain a row with a reason.
The historical combined table expects baseline methods plus the new 120 rows;
read its actual method IDs before assuming a total of 600 rows.

Preserve sample_count=64 at 20x, 96 at 50x; ACM iterations 13/15;
normal_half 2.4/4.0; reset the curvature cycle before each feature as the locked
script does. Keep the 720-angle legacy pathway separate. Current 50x scale
is 0.069 um/px in this config. Read each sequence's sign/nominal step/scale;
nominal commanded stage steps are not independent physical ground truth.
Report repeatability and fixed systematic offset separately.

## 6. Stop/recovery decisions

| Observation | Required action |
|---|---|
| Hash or Raw source mismatch | Do not train; resolve provenance and record a new approved snapshot, never auto-replace hashes |
| W already exists with another identity | Preserve it; resolve the collision before writing anything |
| Wrong units/duplicate keys/invalid flat locator | Repair measurement; rerun affected methods under one protocol ID |
| Gradient absent on active intended parameters | Repair/verify before scientific comparison; preserve failed run |
| GPU OOM | Preserve exact failure and last good checkpoint; bounded microbatch recovery as above, not model/data changes |
| NaN/Inf | Preserve logs/inputs; stop only the exact affected trainer; diagnose before a new attempt |
| Process gone, no summary | Mark interrupted, not complete; check error log/checkpoint and OS shutdown evidence |
| Metric worsens | First audit inputs/protocol; keep valid negative results; follow P04/P09, not automatic smoothing or more epochs |
| No supported change after bounded probes | Write no_supported_change; do not start formal training to fill a checklist |
| Receipt artifact mutated | Revalidate that phase and dependencies; do not bypass audit |
| Confirmation has already been used | Relabel as development; never claim it remains unseen; no repeated selection on it |

There is no resume support in the current R118 trainer. For W, implement and
test exact same-run resume (model, optimizer, scaler, scheduler, RNG, sampler
and completed steps) before offering it. Resume of one interrupted run is
different from initializing a new experiment with previous weights. If exact
resume is unimplemented, retain the interrupted attempt and use a new scratch
attempt with a documented identity; never secretly warm-start.

## 7. Formal completion and final handoff

One formal run is complete only if the same run's marker, child-process exit,
42 unique epoch rows, source/config/data identities, E42 reloadable weights,
final validation, Raw previews and summary agree. Verify no nonfinite values.
No alive process alone can establish progress, and no dead process can prove
success. Keep the last known good epoch and reason on every interruption.

After completion execute P11/P12, then update the canonical experiment report,
MANIFEST, root handoff/index and storage registration without promoting the
production/thesis model automatically. Final user explanation is plain Chinese:
what ran, what improved, what failed, what is still uncertain. Do not list a
wall of unexplained paths or claim a prepared plan is a completed experiment.
