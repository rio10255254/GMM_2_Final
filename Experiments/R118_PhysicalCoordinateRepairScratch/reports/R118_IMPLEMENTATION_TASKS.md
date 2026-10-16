# Next-design implementation cards

Every filename under R119 below is a **future deliverable**, not a currently
available command. Use scripts/next_design.py show Pxx to track the phase.
The new root is denoted W; R118 is denoted B. Absolute roots are in the plan JSON.

## P00 — Refresh facts

Inputs: B/reports/next_design_assets.json and next_design_plan.json.
Run B/scripts/next_design.py audit. It verifies protected hashes, executable
dependencies, Raw inputs, stored data counts, and sealed-manifest status.
Read the current process list and active markers. No inference/training occurs.

Done: audit has no blocking integrity errors; warnings have explicit scope.
If a required hash changed, identify the cause and regenerate the snapshot only
after reading the changed evidence. Never auto-accept changed hashes.

## P01 — Establish isolated work and identity

Before creating W, confirm it does not exist or is exactly the intended resumable
work according to its manifest. Read STARTING_NEW_EXPERIMENT.md.

Create only needed directories: config, model, training, inference, validation,
scripts, reports, results, tests, runs/launcher_logs. Copy the small R118 source
files listed in the asset snapshot, never the entire runs/data/results trees.
Use local source imports and a configuration root argument. Do not import two
different experiments' packages as generic model/training in one interpreter.

Create:
- W/MANIFEST.md (self-contained; source hashes; data roles; expected budget).
- W/config/base_snapshot.json (complete unchanged R118 numerical settings).
- W/config/candidates.json (arm changes explicit).
- W/results/setup_receipt.json.
- A storage registry entry before allocating substantial data.

Reference the immutable R118 base arrays or create verified hardlinks. Never
write through a hardlink. New observations get new paths under W.
Record current Git branch and dirty state. Preserve unrelated changes.
Follow the active branch-prefix instructions; do not blindly switch to main.
No GitHub issue/PR/message is authorized merely by this local plan.

Identity rule: run_id, candidate_id, config snapshot, checkpoint metadata,
inference manifest, and metric method name must agree. If using the legacy
shared trainer, set trainer.MODEL_NAME_BASE = CFG.MODEL_NAME explicitly.
For a native trainer bind that same identity to args.run_id and all artifacts;
do not add an unused legacy variable merely to satisfy a text check.

## P02 — Build measurement before changing the model

Implement:
- W/validation/sequence_metrics.py
- W/validation/calibrate_locators.py
- W/tests/test_sequence_metrics.py

Public interfaces:
- estimate_position(image, fixed_reference, fixed_roi, protocol) -> x, y, valid,
  reason, diagnostics. No model-specific tuning.
- summarize_sequence(position_rows) -> bias, repeatability, step fluctuation,
  tail, cross-axis error, validity counts.
- summarize_paired_effects(sequence_summaries, control_method) -> paired
  per-scene differences plus interval estimates.

Follow R118_MEASUREMENT_CONTRACT.md exactly. Implement validity, units,
population, and uniqueness checks before convenient aggregate plots.
Calibration fixtures must include known translation, photometry-only changes,
center-preserving width changes, dark/bright, cropped and flat cases.

Done: all calibration tests run successfully; JSON includes actual errors and
not-applicable cases. A regression test must prove that pooling distinct
scene biases is NOT reported as one object's repeatability.

## P03 — Build the common bank and run frozen references

Implement:
- W/data/build_sequence_bank.py
- W/data/sequence_bank.py
- W/validation/evaluate_sequence_bank.py

Start with 8 latent scenes to verify storage, geometry replay, and coordinates.
Then build the 48-scene / 4,368-observation DEVELOPMENT bank specified in the
measurement contract. Generate a common input manifest BEFORE inference.
Use recorded scene seeds and 8x rendering; geometry/photometry replay must
match the reference convention. Do not translate already-downsampled labels.

Evaluate Raw and the protected R118 E12 checkpoint. Add R109 E48 as a fixed
reference when its loader/hash checks pass. R109 is not a teacher.
Use separate processes/loaders to avoid import/cache collisions.
Retain identical filenames, coordinates, masks, ROI support, quantization,
and method-independent validity decisions.

Required outputs:
results/frozen_sequences/positions.csv
results/frozen_sequences/steps.csv
results/frozen_sequences/sequence_summary.csv
results/frozen_sequences/audit.json
results/frozen_sequences/representative_panels.png

Done: exact expected observation inventory; static/motion/nuisance are separate;
all invalid observations are present with reasons; no sealed input was used.

## P04 — Locate instability, then choose a bounded mechanism

Implement W/validation/path_interventions.py and evaluate on the SAME bank:

- unchanged frozen R118;
- zero normal shift, with anchor AND downstream width output recomputed;
- neutral width gain=1, retaining the legitimate shift and detail paths;
- detail disabled;
- explicit attenuation control with the same mean correction amplitude as
  any intervention that merely reduces output strength.

Factor out a pure rendering helper in W so the intervention changes one control
before downstream operations. Do not return Raw plus a residual constructed
from a different anchor. Do not edit B's model or save altered weights.

Record per-frame coordinate errors, width/shift maps, endpoint sample positions,
and output amplitude. Perturb one factor at a time: sensor noise, subpixel
phase, exposure, asymmetric blur. Keep the other factors fixed.

Write W/results/mechanism_decision.json:
- dominant_suspect: shift / endpoints_width / estimator / mixed / unresolved;
- evidence paths and paired effects;
- amplitude-control result;
- selected_variant: tangent_coherence / adaptive_endpoints / none;
- explanation and remaining uncertainty.

Selection:
- If only the training locator suggests regression, resolve its calibration or
  validate with the independent/real readout before a model change.
- If shift suppression consistently reduces variance, inspect tangent
  variability. Tangent coherence is a candidate, not automatically selected.
- If width suppression helps and endpoint samples cross another edge, test
  adaptive_endpoints.
- If neither mechanism has repeatable support, choose none and test data-only B.
- A favorable truth-oracle operation is an upper bound, not proof of learnability.

Do not claim the old R116 tangent operation is a new discovery. Cite the
historical evidence and run a matched test with the repaired R118 objectives.

## P05 — Add only the needed training observations

Implement W/data/build_training_observations.py with an explicit --scene-ids
manifest. Existing target arrays remain immutable.

Use the frozen next_design_selected_ids.json, copying its IDs and hash into W.
Short subset: first 512 training IDs, frozen before results. For sequence
enrichment select 4 records per polarity per family from that subset (96
geometries when available). For the future full run expand to 40 per polarity
per family (960), keeping the short subset nested. Enrichment excludes
flat_negative roles; the unchanged base includes all roles.

Generate positions at 8x. At each training step select two observations from
one scene/declared condition; deployment still accepts one image.
Include fixed-optics motion and static repetitions. Put exposure/blur
robustness in separately labeled groups. Do not force action maps to match.

For arm D only, add centered asymmetric-tail and rotated anisotropic blur:
start with broad documented candidate ranges, not a sweep. Kernel sum,
centroid, sampling order, and source/reference photometry must be recorded.
Use the P03/P04 failure slice to select the affected metadata strata, never
choose training examples from validation images.

If kernel centroid is deliberately changed, record the induced coordinate
offset separately; do not silently treat it as stage motion ground truth.
Targets never acquire independent random texture that is absent in the latent.

Before large generation: use the 8-scene pilot's bytes/scene x planned count x
1.25 to estimate disk cost. Prefer compressed sidecars and reference reuse.
Stop duplicate generation by comparing generation signatures, not filenames.

Done: zero train/development/confirmation latent overlap; exact scene counts;
byte-identical reused references; reproducible source observations; realistic
image previews; storage estimate verified.

## P06 — Implement selected candidate and a fair executor

Keep A exactly the current R118 numerical architecture/objective. B changes
only observation scheduling. C adds only the P04-selected mechanism to B.
D adds only asymmetric coverage to B.

Candidate tangent_coherence:
- Local samples along the estimated tangent, not 2D image smoothing.
- Weight by direction agreement and same-boundary support so corners/adjacent
  objects do not average into each other.
- Keep correction strength separately recorded; include amplitude-matched
  control. Preserve a valid local fallback and live gradients.

Candidate adaptive_endpoints:
- Initially compare radii 4, 7, and 10 native pixels around the SAME estimated
  boundary. Record signed-distance progression and extra zero crossings.
- Prefer a span that samples the two sides of one boundary rather than a
  neighboring object. Selection must depend only on local input/predicted maps.
- Start with a deterministic local selector, not a new global learned gate.
- Neutral gain must remain continuous; direct/tiling outputs must agree;
  straight-edge, thin-gap, corner, bright/dark tests must pass.
- If the selector creates rings or is unsupported by P04, omit C.

Executor requirements:
- Explicit --config, --model-seed, --data-seed, --sampler-seed, --scene-ids,
  --run-id, --epochs, --batch, --workers, --output-root.
- Separate seeds for initialization vs observation/noise selection.
- Capture initialization checksum, full configs, source hashes and data IDs.
- Same optimizer-step budget, schedule and input population across arms.
- Every weighted loss must have an intended trainable owner and verified
  nonzero gradient in its active stage.
- All stages keep relevant shape, x/y and pair supervision.
- Known completed-count, batch/epoch timing, validation timing, peak memory,
  checkpoint and preview state in live JSON.
- Unique trainer lock; per-run stdout/stderr; atomic metadata/checkpoints.
- A supervisor owns training completion and subsequent validation. It must not
  rely on an interactive assistant remembering to return after two hours.

Done: CPU behavior tests and GPU all-stage smoke actually run. A dry-run
command manifest is generated and checked for correct roots and identities.
The existing R118 CLI cannot perform this matrix unchanged.

## P07 — Execute matched probes

Use the frozen budgets in the handoff. Seeds are not hyperparameter candidates.
Run one GPU trainer at a time. Launch each arm/seed in a fresh process.
Do not select E12 merely because its filename is last; compare the predefined
stage endpoints and the final endpoint consistently for every arm.
Save E4, E8 and E12 for EVERY probe arm/seed. Primary matched comparisons are
E12 versus E12; E4/E8 describe evolution, not extra independent training arms.

Record expected vs actual steps and initialization checksums. If an arm crashes,
preserve it and rerun the affected comparison under a documented repair version.
Do not silently compare 512-scene/12-epoch probes with 5,000-scene full runs
as though training exposure were equal.

Done: complete per-arm histories, validations and Raw previews; matrix audit
has no missing cell disguised as zero performance.

## P08 — Shortlist external development validation

Use existing locked R73/R74 + shared 36-pillar SEM. Add real LSC through the
versioned adapter described in the runbook. Never use external GMF as the
thesis gate.

Choose a small shortlist from the predefined endpoints, with reasons recorded
before running external tests. Include Raw and R109 references on exactly
matching populations. Do not select favorable frames from model outputs.
Default shortlist: arm A E12 plus at most two supported candidate arms at E12,
using model seed 1185001 selected before outcomes, not the better-looking seed.
Keep the second-seed results in the uncertainty analysis. Add an earlier
endpoint only to investigate a documented stage regression and include the
same epoch's control; never cherry-pick one candidate's best epoch against
another candidate's worst epoch.

Done: shape by family/exposure, detail/ringing, actual Raw provenance,
full/tile parity, and real LSC results; measurement uncertainty and failures
retained. Label all these reused populations development.

## P09 — Choose the full-run design

Write W/results/design_decision.json containing:
selected_arm (A/B/C/D/CD/no_supported_change/inconclusive), full_run_justified;
model/data/config/seed versions; main gains; regressions; uncertainty;
what was NOT tested; justification for a full run.

Use the handoff decision rules. A combined C+D needs its own small interaction
probe. Do not infer additive benefits. Do not pick one universal weighted score.
If no supported change exists, close the probe phase and report that result.
Do not fill the full-training slot just because it exists in this document.

## P10 — One formal scratch run

Only after plan activation and a supported decision:
- 5,000 training geometries; untouched development/confirmation partitioning.
- 42 epochs unless a revised tested schedule is explicitly recorded.
- Batch 12, workers 4 as the initial measured setting.
- No weights from R61/V42/R109/R117/R118 probes.
- Set runs/launcher_logs/active_formal_run.json before training.
- Exact unique run_id in every artifact and supervisor record.
- Checkpoints and true-Raw previews every 3 epochs, including E42.
- Keep all prior unsuccessful attempts; no hidden deletion/relabeling.

Run the documented supervisor. Completion requires actual E42 weights,
42 epoch rows, final validation and previews, summary, finite reload/inference,
and the trainer process exited. A missing process alone is NOT completion.
The receipt must hash the actual E42 checkpoint, log, config, final preview and
validation artifacts, not only a JSON statement that they exist. If checksums
or run IDs disagree, the completion summary is invalid even if it says pass.

## P11 — Full model validation and analysis

Repeat P08 using the full model and the predefined stage checkpoints where
available. Include real sequence stability, not only synthetic fit or image
energy. Inspect final images, not only plots or JSON flags.
If apparently worse, first verify input, units, method, population and frozen
protocol before inventing another architecture explanation.

Done: W/reports/R119_RESULTS.md with measured capability and limits.
Do not automatically replace the thesis model or enterprise package.

## P12 — Confirmation and closeout

Freeze the candidate/config/decision, then use the 144-scene confirmation once.
Evaluate every required readout on the same candidate. No tuning on its results.
Keep R118's immutable seal manifest unchanged. Record the candidate hash,
input seal hash, first evaluation time and outputs in
W/results/confirmation/consumption.json, and update the root handoff to say the
set has been consumed. The historical source seal is not permission to reuse it
as unseen. If confirmation fails, record failure. Future tuning requires a NEW final
confirmation set; do not keep calling this one unseen.

Update project handoff/index/storage and the experiment MANIFEST. Preserve
the formal baseline unless the user explicitly decides to promote a model.
If a monitor was created for this run, remove it after completion/failure
resolution and say it stopped. Keep canonical reports; don't edit stale mirrors.
