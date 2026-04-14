# 可編輯真源 vs 鏡像政策 / Source of Truth Policy

Last updated: 2026-04-08

## 核心規則

**只在 canonical source 編輯。鏡像只讀、只引用，不直接修改。**

專案控制與整體巡檢請使用 `python Tools/project_control_center.py`；它只整合這份政策與其他正式文件，不取代它們。

## 分類

### 實驗報告

| 類型 | Canonical (可編輯) | Mirror (只讀) |
|------|-------------------|--------------|
| R33 實驗報告 | `Experiments/R33RobustLoss/reports/*.md` | — |
| R38v2/COMBO 報告 | `Experiments/R38v2SeqFixed/reports/*.md` | — |
| R32 external compare | `Experiments/R32Sandbox/reports/ROUND32_EXTERNAL_COMPARE.md` | `docs/evidence/falsified/ROUND32_EXTERNAL_COMPARE.md`（鏡像） |
| R31 external compare | `Traing_Progress/organized_20260316/round31/selected/reports/ROUND31_EXTERNAL_COMPARE.md` | `docs/evidence/falsified/ROUND31_EXTERNAL_COMPARE.md`（curated copy） |
| R30 baseline proof | — (來源在 Traing_Progress/) | `docs/evidence/baseline/ROUND30_EXTERNAL_COMPARE.md`（curated copy） |

**規則**：
- `Experiments/*/reports/` 是 R33+ 實驗報告的**主要可編輯位置**
- **R26 例外**：R26NewPSFCheck 的 canonical 報告分佈在多個子目錄（`psf_audit/`、`formal_newpsf_candidate/reports/`、`pure_psf_control/reports/`、`root_cause_centering/reports/`），這些都是 canonical，不是 mirror。R26 的結構是歷史產物，見 `docs/operations/QUIRKS.md` §4。
- `docs/evidence/` 裡的 R30/R31 檔案是從 `Traing_Progress/` 複製的歷史 curated copy，原始來源不在 Experiments/

### docs/evidence/ 鏡像政策（2026-04-14 更新）

`docs/evidence/*` 下的 20 份 curated copy 是**可能與 canonical drift 的穩定引用錨點**，專供論文、對外報告的穩定路徑使用。

- **以 canonical 為準**：任何分析結論要以 canonical source 為依據，不以 mirror 為準
- **不強制同步**：修改 canonical 後**不需要**同步 mirror（CLAUDE.md 的 Documentation update policy 已將此項移出 mandatory 列表）
- **mirror 可落後**：只有當 mirror 與 canonical 的差異顯著影響引用理解時，才手動 refresh
- canonical source 見下方各類型的 canonical location 欄位

### Legacy batches (`organized_20260313`-`organized_20260316`)

| 類型 | Canonical (可編輯) | Mirror (只讀) |
|------|-------------------|--------------|
| `organized_20260313/root_status_legacy` 狀態快照 | `Traing_Progress/organized_20260313/root_status_legacy/*.md/json` | `docs/archive/legacy_runtime_status/*` curated copies where present |
| `Round16`-`Round19` 決策鏈 | `Traing_Progress/organized_20260313/roundXX/selected/reports/*.md/json` | `docs/evidence/*` curated copies where present |
| `Round20` process probe | `Traing_Progress/organized_20260314/round20/ROUND20_POSTMORTEM.md`, `Traing_Progress/organized_20260314/round20/selected/reports/*.md/json` | `docs/evidence/*` curated copies where present |
| `diagnostics` 分支決策 | `Traing_Progress/organized_20260314/diagnostics/*.md/json` | `docs/evidence/*` curated copies where present |
| `branch_e` estimator probe | `Traing_Progress/organized_20260314/branch_e/selected/reports/*.md/json` | `docs/evidence/*` curated copies where present |
| `Round21` / `Round22` 決策鏈 | `Traing_Progress/organized_20260315/roundXX/ROUND2X_POSTMORTEM.md`, `Traing_Progress/organized_20260315/roundXX/selected/reports/*.md/json` | `docs/evidence/*` curated copies where present |
| `pairwise_delta_probe` | `Traing_Progress/organized_20260315/pairwise_delta_probe/selected/reports/*.md/json` | `docs/evidence/*` curated copies where present |
| `branch_e_followup` | `Traing_Progress/organized_20260315/branch_e_followup/BRANCH_E_PHASE2_POSTMORTEM.md`, `Traing_Progress/organized_20260315/branch_e_followup/selected/reports/*.md/json` | `docs/evidence/*` curated copies where present |
| `estimator_formula_probe` | `Traing_Progress/organized_20260315/estimator_formula_probe/selected/reports/*.md/json` | `docs/evidence/*` curated copies where present |
| `Round23`-`Round31` 決策鏈 | `Traing_Progress/organized_20260316/roundXX/selected/reports/*.md/json` | `docs/evidence/*` curated copies where present |
| `Round18` vs `Round22` compare | `Traing_Progress/organized_20260316/external_compare_round18_round22/reports/*.md/json` | `docs/evidence/historical_baselines/*` curated summaries |
| `Round25`-`Round29` compare chain | `Traing_Progress/organized_20260316/external_compare_*/reports/*.md/json` | `docs/evidence/historical_baselines/*` curated summaries |
| `Round30` final external proof | `Traing_Progress/organized_20260316/round30/selected/reports/ROUND30_EXTERNAL_COMPARE.md` | `docs/evidence/baseline/ROUND30_EXTERNAL_COMPARE.md` |
| TTA side direction | `Traing_Progress/organized_20260316/tta_experiment/r26_tta_cross5/reports/*.md/json` | `docs/evidence/side_directions/TTA_VS_BASELINE_CROSS5_COMPARISON.md/json` |
| Screening analysis | `Traing_Progress/organized_20260316/analysis/INTERNAL_EXTERNAL_CORRELATION.md/json` | `docs/evidence/analysis/INTERNAL_EXTERNAL_CORRELATION.md/json` |

**規則**：
- `Traing_Progress/organized_20260313/` 到 `Traing_Progress/organized_20260316/` 都是 preserved historical working surfaces；補導引層，不重構原始 evidence layout。
- `round16`-`round19`、`round20`、`round21`、`round22`、`round23`-`round31` 的 canonical decision surface 在各自的 `selected/reports/`；若 root 另有 `POSTMORTEM.md`，它也是 canonical。
- `diagnostics/`、`pairwise_delta_probe/`、`branch_e/`、`branch_e_followup/`、`estimator_formula_probe/` 的 canonical surface 在各自 root 或 `selected/reports/`，依上表為準。
- `external_compare_round18_round22/` 與 `external_compare_*` 的 canonical compare surface 在各自的 `reports/`；沒有 `reports/` 的 payload-only compare directories 只保留 raw recon / GMF，不是 mirror。
- `docs/evidence/` 對這批 legacy batches 仍是 curated mirror / index，除非 policy 明確說它本身就是索引層（例如 `EVIDENCE_MAP.md`）。
- `round32/` 雖然仍保留在 `Traing_Progress/organized_20260316/`，但 canonical 治理面已移到 `Experiments/R32Sandbox/`，不要在兩處同時維護。
- 操作入口請先看 `docs/operations/LEGACY_ROUNDS_OPERATIONS.md`，不要直接把長河歷史文件當成 editable source。

### 治理文件

| 文件 | 角色 | 編輯規則 |
|------|------|---------|
| `ESTIMATOR_POLICY.json` | Machine-readable baseline truth | 直接編輯 |
| `PROJECT_STATE.md` | Human-readable current state | 直接編輯 |
| `PROJECT_STATE.md` | Cross-session handoff | 直接編輯 |
| `PROJECT_ARCHITECTURE.md` | Stable rules | 直接編輯 |
| `docs/analysis/RESEARCH_PATHS.md` | Research path visualization | 直接編輯 |
| `docs/evidence/EVIDENCE_MAP.md` | Evidence chain index | 直接編輯（它是索引，不是內容） |
| `Experiments/INDEX.md` | Experiment quick reference | 直接編輯 |
| `README.md` | Project overview | 直接編輯（從治理文件摘要，非 canonical source） |

### PSF 政策

| 文件 | 角色 |
|------|------|
| `docs/policy/PSF_STANDARD_POLICY.json` | PSF policy canonical source |
| `docs/policy/PSF_POLICY_TRANSITION_R26.md` | Transition rationale（歷史文件，不再修改） |

### 推理腳本

| 文件 | 角色 |
|------|------|
| `Model/GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py` | **Canonical**（主線推理） |
| `Model/GeoEdgeAlignSR_v1_Infer_TTA.py` | Canonical（TTA 推理） |
| `_deployment_package/.../Infer_v5...SimpleTest.py` | **Mirror**（部署包副本） |
| `Experiments/R26NewPSFCheck/.../Infer_v5...SimpleTest.py` | **Mirror**（R26 package clone） |

**修改推理腳本時，必須同步更新所有 mirror 副本。**
目前有 4 份 Infer_v5 腳本需要保持一致（見 `QUIRKS_AND_CONVENTIONS.md` §7）。

## AI Agent 指令

當你要修改一個檔案時：
1. 先確認它是 canonical source 還是 mirror
2. 如果是 mirror → 找到 canonical source → 在那邊改 → 同步 mirror
3. 如果不確定 → 搜尋 `SOURCE_OF_TRUTH_POLICY.md` 的分類表
4. 搜尋到同名檔案出現在多處時 → 問使用者哪個是 canonical
