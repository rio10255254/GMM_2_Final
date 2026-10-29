# R118 next-design execution handoff

Status: **EXECUTED AND VERIFIED (P00–P12)**. This is the canonical plan; R119
completion receipts are the execution evidence.
Authoritative current artifacts: READY.json, reports/next_design_assets.json,
reports/next_design_plan.json, and runs/RUN_INDEX.json.

## 1. Read in this order

1. AGENTS.md and PROJECT_STATE.md.
2. This document completely.
3. R118_MEASUREMENT_CONTRACT.md.
4. R118_IMPLEMENTATION_TASKS.md.
5. R118_OPERATION_RUNBOOK.md.
6. Run scripts/next_design.py audit and next.

Do not reread every historical round. Follow the specific historical source
links below when a task calls for them.

## 2. User objective and boundaries

The thesis objective is accurate ACM shape, stable displacement, and clear,
faithful detail. The deployed model accepts **one image** and must support
large-image tiling. Multiple synthetic observations are training/validation
supervision only.

- Keep approximately 5,000 independent training geometries.
- Draw labels at 8x resolution before sensor integration.
- No real SEM/HS100MG pixels or copied sample structures in training.
- Instrument statistics may inform simulation; do not call guessed kernels
  measured microscope PSFs.
- Every independent training arm starts with random weights. Historical
  checkpoints are inference references, never initialization or teachers.
- Keep training, inference, data, weights, manifests, and monitoring inside
  the new work folder. Link immutable shared payload rather than duplicating it.
- External GMF is an industry matter, **not a thesis selection requirement**.
  Generic older GMF-promotion rules do not override the user's explicit scope.
- Fixed bias and repeatability must be reported separately. A stable bias is
  not automatically instability; shape accuracy must still be checked.
- No single composite score or arbitrary percentage veto should silently
  decide scientific tradeoffs. Hard checks are for invalid experiments,
  leakage, broken execution, wrong units, and unsafe file/process operations.
- Do not promise that all metrics will improve or that more epochs will fix
  an unresolved mechanism.

This preparation request does not itself launch further experiments. When
the user subsequently activates this plan, execute the ordered local work
without asking permission again for each ordinary step. A request to execute
the whole plan includes the bounded probes and one selected 42-epoch run.
If scientific results remain genuinely ambiguous after the specified repeat,
report the concrete alternatives instead of inventing a winner.

## 3. Current verified state

Experiment root:
Experiments/R118_PhysicalCoordinateRepairScratch

| Item | Verified value | Meaning |
|---|---|---|
| R118 formal training | Not started | Do not call its E12 probe a full model |
| Latest repaired probe | runs/verified_physical_repair/weights/epoch_012.pth | 512 training scenes, 12 probe epochs |
| Checkpoint SHA-256 | b83b7748f7d128793f6e198b23242c114cae1ee6b25734a718d9d68bba515ecd | Exact inference reference |
| Prepared base data | 5,000 train + 512 development validation | Not all used by the short probe |
| Confirmation data | 144 scenes, unopened for model evaluation | Preserve the entire data/confirmation tree |
| R74 full development ACM | Median per-image boundary distance 7.2417585 -> 6.7315455 px | 7.0454% reduction; not a new sealed test |
| R74 asymmetric blur/halo | Boundary distance +8.2335% | Real negative result, do not hide |
| SEM development comparison | 36/36 independent pillars improved; median paired gain 0.1037899% of pitch | 12 repeated exposures are not 432 independent pillars |
| Real-crop tile parity | Maximum 0.0026751 gray | Verified on the trained probe |
| Short-run paired X dispersion | Raw 0.0280659, R118 0.0329429 px | Mixed-scene two-view diagnostic, NOT real sequence repeatability |
| Short-run paired Y dispersion | Raw 0.0303740, R118 0.0347351 px | Same limitation |
| With/without detail control | X dispersion 0.0331627 / 0.0330385 px | No evidence that removing detail solves motion |

The current root formal production baseline remains COMBO in
ESTIMATOR_POLICY.json. V42 is the historical thesis-results reference, R61
has a separate legacy/delivery role, R109 E48 is a strong clean-training
research reference, and R118 E12 is a repair probe. Do not merge these roles.

The repository currently contains many user/archive changes, on branch
sandbox/r98-aggressive-texture-scratch. This is a snapshot, not a command to
switch branches. Read current Git state before any future branch operation.
Never reset/clean/stash the whole workspace to make an experiment convenient.

## 4. Important corrections to past interpretation

1. Earlier R117 real previews fed **R109 outputs into R117**. Correct Raw files
   now live under R118 validation/inputs/Raw and are checksum-locked.
2. R117's signed-distance/normal mismatch was a real implementation error.
   Its reflection/high-pass protection could create rings.
3. Logged loss existence did not imply learning. The old SDF pair term had
   zero gradient to the active parameters; E6/E42 detector weights were equal.
4. The old whole-object signed radial average was not an x/y locator.
5. Mixed-scene pair dispersion is not the repeatability of one moving object.
6. A smaller horizontal gradient-energy value is not proof of lost detail.
7. R109 R73/R74 historical tables retain a stale method label R61v16. Resolve
   identity from their inference manifest and checkpoint hash, not that label.
8. The selected R118 checkpoint's config predates packaging-only Raw path
   changes. The input bytes, numerical model, and default schedule agree.
9. The R118 orientation experiment folder named final_repair_detail is a
   rejected variant. Names containing final are not selection evidence.
10. R118 data/confirmation remains untouched by model selection. Inspect its
    manifest/hashes for integrity, not images or model outputs during probes.

Evidence: the R117 analysis/design_audit_20260905 directory; R118 READY.json;
reports/REPAIR_MAP.md; results/probe_comparison.json; runs/RUN_INDEX.json.

## 5. The next questions, in order

Q1: Does the apparent motion regression persist for repeated observations of
the SAME object under fixed optics, and on the locked real LSC readout?

Q2: When it persists, is it associated with normal-shift control, width
rendering/endpoints, detail, image quantization, or the coordinate estimator?

Q3: Do coherent same-object sequence observations improve learning without
removing current shape/detail benefits?

Q4: Does one bounded geometric-control change improve the diagnosed failure,
and does targeted asymmetric-blur coverage help independently?

Q5: Which tested design merits ONE full scratch training run?

Do not begin with a larger network, longer run, stronger identity penalty,
output smoothing, or a broad detail shutdown. Those are not supported by
the existing diagnosis.

## 6. Phase map

| Phase | Work | New implementation? | Required result |
|---|---|---|---|
| P00 | Refresh current facts and protect references | No; helper exists | passing input audit |
| P01 | Create isolated next work folder and record identity/storage | Yes | setup receipt and source snapshot |
| P02 | Implement measurement contracts and calibration fixtures | Yes | locator tests and artifact schemas pass |
| P03 | Build development sequence bank; evaluate frozen references | Yes | separate repeat/bias/motion/nuisance results |
| P04 | Recompute frozen path interventions and diagnose sensitivity | Yes | one causal decision, with limits |
| P05 | Build only necessary sequence/asymmetry observation sidecars | Yes | leakage-free, complete, deterministic data |
| P06 | Implement selected geometric variant and shared executor | Conditional | mechanism tests and fair command plan |
| P07 | Run matched small scratch arms | After activation | fixed-budget multi-arm results |
| P08 | Validate shortlist with ACM, SEM, real LSC and visual/tile checks | Adapter work | same-population comparison |
| P09 | Select design or state inconclusive | Scientific decision | explicit evidence-based decision.json |
| P10 | One complete 42-epoch scratch training | Conditional | exact run identity and completion artifacts |
| P11 | Full posttraining development validation | Yes | model capability with all failures retained |
| P12 | One final confirmation and closeout | After design is frozen | confirmation report; no automatic promotion |

The full cards are in R118_IMPLEMENTATION_TASKS.md. The machine-readable
dependency graph is next_design_plan.json. Nothing from P01 onward is claimed
to be implemented merely because it has an assigned filename.

## 7. Default budgets and experiment identities

Proposed next root: Experiments/R119_SequenceGeometryValidation.
It is a PLANNED path, not an existing runnable package. If it already exists
when activated, inspect its manifest and stop before overwriting or choosing
an unrecorded alternate name.

Initial development bank: 48 geometries, selected by metadata only from the
512 development scenes: 12 families x 2 polarities x 2 scenes. Use the lowest
scene IDs satisfying each stratum, excluding flat_negative roles for position
experiments. Exact selections are frozen in reports/next_design_selected_ids.json
(48 bank / 512 probe / 96 short enrichment / 960 full enrichment). Use those
IDs, not a fresh sample. All strata have enough records and short enrichment
is nested in full enrichment. If a stratum becomes short after a version change,
record the deficit;
do not use sealed scenes as substitutes.

Short training: 512 fixed training scene IDs, 12 epochs, stages 4/4/4, two
model seeds (1185001, 1185002), batch 8, workers 2. Data/sampler seeds are held
identical across arms within a replicate and kept separate from model seed.
Use data_seed=1196001, sampler_seed=1197001 in both replicates to isolate model
initialization variation. Bank seed is 1198001; per-observation seeds use a
recorded stable integer mapping, not Python's salted hash(). The future formal
scratch model seed is 1195001. Save probe E4/E8/E12 explicitly; formal
checkpoints/previews remain every three epochs.
Arm A: current R118 numerical model/objective and original two-view scheduling.
Arm B: A + coherent-sequence observation scheduling only.
Arm C: B + the single geometric change selected in P04 only; omit if unsupported.
Arm D: B + targeted asymmetric-blur observations only; do not silently merge D
into C. A combined arm is allowed only after C and D individually have support;
one bounded interaction probe, not a new search.

Maximum initial matrix: 4 arms x 2 seeds x 12 epochs. No hyperparameter sweep.
One additional repeated control is allowed if numerical variation makes a
small apparent effect ambiguous. Do not use the confirmation set to settle it.

Formal plan: 5,000 training geometries, 42 epochs, batch 12, workers 4,
checkpoints/previews every 3 epochs, all development loss groups retained.
Keep geometry active after warmup; freeze/schedule decisions must be tested
in the probe version rather than improvised during the formal run.

Storage: reuse immutable reference arrays. Initial new sidecars/reconstructions
budget 8 GiB; estimate actual bytes before generation. If the estimate exceeds
it, first reduce redundant exports/compress sidecars; do not delete history.
Current available space is a live-read fact, not the dated root registry value.

## 8. Scientific decision rules, without a fake universal score

- Invalid units, wrong inputs, train/validation overlap, broken gradients,
  missing outputs, nonfinite values, or a non-scratch start invalidate an arm.
  Repair and rerun the affected comparison. Do not reinterpret these as tradeoffs.
- Evaluate repeatability, fixed bias, ACM shape, faithful detail, and artifacts
  separately, with per-family/per-condition results and uncertainty.
- A result supported only by the training locator is insufficient. Check an
  independent readout and the real locked LSC path before a motion claim.
- If one candidate has reproducible benefit and no material loss on the other
  target axes, select it for the full experiment, not for product promotion.
- If there is a genuine scientific tradeoff, describe its size and uncertainty.
  Prefer the simpler change when effects cannot be distinguished.
- If no tested change has support, retain R118 as reference and record
  no_supported_change. Do not launch a long run simply to complete the checklist.
- When two reasonable options remain after the one allowed repeat, the executor
  may request one concrete decision using the actual comparison. Do not ask the
  user to redesign the experiment or to debug commands.

## 9. Required closeout language

State what was implemented, which experiments actually ran, which model/data
versions were compared, what improved, what did not, and what remains uncertain.
Never equate preparation, smoke success, training completion, a lower loss,
or an unopened confirmation manifest with proven model capability.

No external messages, GitHub issue/PR changes, delivery ONNX export, or model
promotion are implied by this local handoff. Follow any explicit later user
authorization without adding redundant approval steps.
