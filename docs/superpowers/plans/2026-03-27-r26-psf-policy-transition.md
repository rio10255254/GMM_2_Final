# R26 PSF Policy Transition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote the new physically justified PSF to the current research standard while preserving the old PSF as a legacy empirical baseline, and update the R26 package only after a same-recipe replacement checkpoint exists.

**Architecture:** Treat this as a policy transition, not a one-file swap. The transition has three layers: policy/provenance, same-recipe candidate production, and package/root promotion. The package must not point to a “new PSF standard” while still shipping the old `r26_sm035` checkpoint, because inference defaults currently rely on checkpoint-embedded PSF buffers.

**Tech Stack:** PowerShell launchers, Python training/inference scripts, JSON manifests, Markdown docs, `pytest`, existing package smoke flow.

---

## File Map

**Create**
- `docs/policy/PSF_POLICY_TRANSITION_R26.md`
- `docs/policy/PSF_STANDARD_POLICY.json`
- `Experiments/R26NewPSFCheck/formal_newpsf_candidate/README.md`
- `Experiments/R26NewPSFCheck/formal_newpsf_candidate/candidate_manifest.json`
- `Experiments/R26NewPSFCheck/formal_newpsf_candidate/reports/NEW_PSF_FORMAL_R26_COMPARE.md`
- `Experiments/R26NewPSFCheck/package_policy_transition/tests/test_psf_policy_transition.py`
- `Deliverables/Company_Packages/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/參考文件/R26_LEGACY_BASELINE_MANIFEST.md`

**Modify**
- `PSF_Fitting/Crop_circle_FreqFiltered/Fits/PSF_fitted_2D_FOVstack.mat`
- `PSF_Fitting/Crop_circle_FreqFiltered/Fits/formal_config.json`
- `Deliverables/Company_Packages/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/內部檔案/PSF_Fitting/Crop_circle_FreqFiltered/Fits/PSF_fitted_2D_FOVstack.mat`
- `Deliverables/Company_Packages/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/內部檔案/formal_r26_recipe.json`
- `Deliverables/Company_Packages/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/參考文件/R26_FORMAL_REPRO_MANIFEST.md`
- `Deliverables/Company_Packages/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/使用說明.md`
- `Deliverables/Company_Packages/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/檔案結構說明.md`
- `Deliverables/Company_Packages/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/內部檔案/Model/README.md`
- `Experiments/R26NewPSFCheck/package_repro_validation/tests/test_r26_formal_package.py`

**Use / Inspect**
- `Traing_Progress/auto_tune_reports/auto_tune_report_20260316_185417.json`
- `Traing_Progress/organized_20260316/round26/selected/current_round26_step_recovery_seed.json`
- `Traing_Progress/organized_20260316/round26/archive/runs/training_progress_GESR_v1_v5_ST0p8_SWP_r26sm035_20260316_190408/weights/best_tradeoff.pth.tar`
- `Traing_Progress/organized_20260316/round25/archive/runs/training_progress_GESR_v1_v5_ST0p8_SWP_r25sw010_20260316_173027/weights/best_tradeoff.pth.tar`
- `Deliverables/Company_Packages/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/內部檔案/GeoEdge_PackageSmokeTest.ps1`
- `Deliverables/Company_Packages/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/內部檔案/GeoEdge_NativeLauncher.ps1`

## Non-Negotiable Decision Boundary

- The new PSF may become the **current standard**, but only after a **same-recipe replacement checkpoint** exists.
- Do **not** promote “new PSF standard” while package inference still ships the old `r26_sm035_best_tradeoff.pth.tar`.
- Old PSF is not deleted. It becomes `legacy empirical baseline`.

## Task 1: Freeze Policy and Provenance

**Files:**
- Create: `docs/policy/PSF_POLICY_TRANSITION_R26.md`
- Create: `docs/policy/PSF_STANDARD_POLICY.json`
- Create: `Deliverables/Company_Packages/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/參考文件/R26_LEGACY_BASELINE_MANIFEST.md`
- Modify: `Deliverables/Company_Packages/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/參考文件/R26_FORMAL_REPRO_MANIFEST.md`

- [ ] **Step 1: Write the failing policy test**

Add assertions in `test_psf_policy_transition.py` that require:
- a machine-readable policy file to exist
- the policy to distinguish `current_standard` vs `legacy_baseline`
- the package to carry both a current formal manifest and a legacy baseline manifest

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
pytest Experiments/R26NewPSFCheck/package_policy_transition/tests/test_psf_policy_transition.py -q
```

Expected: FAIL because the policy and legacy manifest do not exist yet.

- [ ] **Step 3: Write minimal policy/provenance artifacts**

Document:
- why the research standard moves to the new PSF
- why the old PSF remains archived
- what “formal current standard” means
- what “legacy empirical baseline” means
- which reports still cite the legacy line

- [ ] **Step 4: Re-run test**

Run the same `pytest` command and confirm the new policy artifacts are present and parseable.

- [ ] **Step 5: Commit**

```powershell
git add docs/policy/PSF_POLICY_TRANSITION_R26.md docs/policy/PSF_STANDARD_POLICY.json Experiments/R26NewPSFCheck/package_policy_transition/tests/test_psf_policy_transition.py Deliverables/Company_Packages/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/參考文件/R26_LEGACY_BASELINE_MANIFEST.md Deliverables/Company_Packages/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/參考文件/R26_FORMAL_REPRO_MANIFEST.md
git commit -m "docs: define R26 PSF standard transition policy"
```

## Task 2: Produce a Same-Recipe New-PSF Candidate

**Files:**
- Create: `Experiments/R26NewPSFCheck/formal_newpsf_candidate/README.md`
- Create: `Experiments/R26NewPSFCheck/formal_newpsf_candidate/candidate_manifest.json`
- Modify: `Deliverables/Company_Packages/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/內部檔案/formal_r26_recipe.json` only in a cloned or sandboxed candidate package copy

- [ ] **Step 1: Clone the current formal package into a candidate workspace**

Create a candidate copy under:
`Experiments/R26NewPSFCheck/formal_newpsf_candidate/package_clone`

Do not edit the shipping package yet.

- [ ] **Step 2: Write a candidate manifest before touching the clone**

Record:
- source package path
- new PSF source path + hash
- old PSF legacy hash
- deployed checkpoint hash
- seed checkpoint hash
- exact recipe hash / timestamp

- [ ] **Step 3: Change only the formal PSF reference in the clone**

In the clone:
- replace the packaged PSF file with the new physically justified PSF
- update `formal_r26_recipe.json` hashes and PSF path metadata
- keep train/infer scripts, seed, selected stages, launchers unchanged

- [ ] **Step 4: Verify recipe parity**

Run a parity check that proves:
- same seed
- same deterministic mode
- same selected stages
- same model scripts
- same deploy/seed checkpoint layout
- only PSF-related fields differ

- [ ] **Step 5: Launch a same-recipe formal candidate run**

Run the cloned package’s formal flow, not generic experimentation:
- formal train dry-run
- front-stage actual train probe
- candidate full-train if the probe is clean

Required run identity:
- same historical `r26_sm035` recipe
- new PSF only

- [ ] **Step 6: Commit candidate manifest updates**

```powershell
git add Experiments/R26NewPSFCheck/formal_newpsf_candidate/README.md Experiments/R26NewPSFCheck/formal_newpsf_candidate/candidate_manifest.json
git commit -m "exp: stage formal new-PSF package candidate"
```

## Task 3: Compare the New-PSF Candidate Against Legacy Formal R26

**Files:**
- Create: `Experiments/R26NewPSFCheck/formal_newpsf_candidate/reports/NEW_PSF_FORMAL_R26_COMPARE.md`
- Use existing comparison/test assets from `package_repro_validation` and single-image analysis scripts

- [ ] **Step 1: Write the failing comparison test**

Require the comparison report to include:
- same-recipe confirmation
- candidate checkpoint path
- legacy checkpoint path
- single-image comparison summary
- smoke/demo inference status
- explicit verdict: promote or hold

- [ ] **Step 2: Run test to verify it fails**

Run the comparison test and confirm it fails because the report does not exist yet.

- [ ] **Step 3: Generate the comparison report**

Minimum contents:
- package usability status
- same-recipe parity statement
- key metrics deltas vs legacy baseline
- note that slight regression may be acceptable under the new physics policy
- identify unacceptable cases only if there is clear breakage or severe degradation

- [ ] **Step 4: Re-run test**

Run the same test and confirm the comparison artifact is present and structured.

- [ ] **Step 5: Commit**

```powershell
git add Experiments/R26NewPSFCheck/formal_newpsf_candidate/reports/NEW_PSF_FORMAL_R26_COMPARE.md
git commit -m "docs: record formal new-PSF candidate comparison"
```

## Task 4: Promote the New PSF to Root and Package Defaults

**Files:**
- Modify: `PSF_Fitting/Crop_circle_FreqFiltered/Fits/PSF_fitted_2D_FOVstack.mat`
- Modify: `PSF_Fitting/Crop_circle_FreqFiltered/Fits/formal_config.json`
- Modify: `Deliverables/Company_Packages/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/內部檔案/PSF_Fitting/Crop_circle_FreqFiltered/Fits/PSF_fitted_2D_FOVstack.mat`
- Modify: `Deliverables/Company_Packages/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/內部檔案/formal_r26_recipe.json`
- Modify package manifests/docs listed in File Map

- [ ] **Step 1: Archive the legacy PSF before replacing defaults**

Copy the old PSF into a stable legacy location and record its hash in both root and package provenance docs.

- [ ] **Step 2: Promote the new PSF into the formal default path**

Update the root and package formal PSF paths to the new fitted result.

- [ ] **Step 3: Promote the replacement formal checkpoint together with the PSF**

If Task 2 produced an accepted candidate checkpoint, replace:
- formal package deployed checkpoint
- root formal deploy reference

Do not promote the new PSF alone while keeping the old embedded-PSF deploy checkpoint.

- [ ] **Step 4: Update docs and language**

All docs must now say:
- `current standard`: new PSF
- `legacy baseline`: old PSF
- package meaning: current research standard package

- [ ] **Step 5: Re-run package validation**

Run:
```powershell
pytest Experiments/R26NewPSFCheck/package_repro_validation/tests/test_r26_formal_package.py -q
powershell -NoProfile -ExecutionPolicy Bypass -File Deliverables/Company_Packages/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/內部檔案/GeoEdge_PackageSmokeTest.ps1 -InferenceSampleCount 1 -SkipTrain
```

Expected:
- package tests pass
- smoke test prints `SMOKE TEST OK`

- [ ] **Step 6: Commit**

```powershell
git add PSF_Fitting/Crop_circle_FreqFiltered/Fits/PSF_fitted_2D_FOVstack.mat PSF_Fitting/Crop_circle_FreqFiltered/Fits/formal_config.json Deliverables/Company_Packages/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包
git commit -m "feat: promote new PSF as current R26 standard"
```

## Task 5: Final Acceptance Verification

**Files:**
- Modify or create only if verification reveals a real issue

- [ ] **Step 1: Verify formal asset hashes**

Run a script that prints:
- current standard PSF hash
- legacy baseline PSF hash
- current deploy checkpoint hash
- legacy deploy checkpoint hash

- [ ] **Step 2: Verify root/package script parity**

Run a parity check on:
- `GeoEdgeAlignSR_v1_ModelA_v5_NoCoord.py`
- `GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py`
- `GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py`

- [ ] **Step 3: Verify package behavior**

Run:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Deliverables/Company_Packages/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/內部檔案/GeoEdge_NativeLauncher.ps1 -Action show-config
powershell -NoProfile -ExecutionPolicy Bypass -File Deliverables/Company_Packages/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/內部檔案/GeoEdge_R26_FormalTrain.ps1 -Action dry-run
powershell -NoProfile -ExecutionPolicy Bypass -File Deliverables/Company_Packages/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/內部檔案/GeoEdge_R26_FormalInfer.ps1 -Action dry-run-demo -InputDir Deliverables/Company_Packages/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/內部檔案/Demo_Input -ReconRoot Deliverables/Company_Packages/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包/輸出結果/推論結果
```

Expected:
- launcher emits config JSON
- train wrapper emits valid dry-run JSON
- infer wrapper emits valid dry-run JSON

- [ ] **Step 4: Write final verdict note**

Summarize:
- what is now the current standard
- what is archived as legacy
- whether the package is ready for day-to-day use
- whether a new formal long-run still remains to be completed

- [ ] **Step 5: Commit**

```powershell
git add docs/policy Experiments/R26NewPSFCheck/formal_newpsf_candidate Deliverables/Company_Packages/GeoEdge_R26_正式交付版/GeoEdge_R26_使用包
git commit -m "chore: finalize R26 PSF policy transition"
```

## Acceptance Criteria

- Package launchers remain easy to use.
- Root and package both clearly distinguish `current standard` and `legacy baseline`.
- The package no longer mixes “historical best empirical result” language with “current physically justified standard” language.
- The new PSF is promoted only together with a same-recipe candidate checkpoint, not as an orphan file swap.
- Verification commands pass with fresh output.
