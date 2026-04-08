# 可編輯真源 vs 鏡像政策 / Source of Truth Policy

Last updated: 2026-04-08

## 核心規則

**只在 canonical source 編輯。鏡像只讀、只引用，不直接修改。**

## 分類

### 實驗報告

| 類型 | Canonical (可編輯) | Mirror (只讀) |
|------|-------------------|--------------|
| R33 實驗報告 | `Experiments/R33RobustLoss/reports/*.md` | — |
| R38v2/COMBO 報告 | `Experiments/R38v2SeqFixed/reports/*.md` | — |
| R32 external compare | `Experiments/R32Sandbox/reports/ROUND32_EXTERNAL_COMPARE.md` | `docs/evidence/falsified/ROUND32_EXTERNAL_COMPARE.md`（鏡像） |
| R31 external compare | — (來源在 Traing_Progress/) | `docs/evidence/falsified/ROUND31_EXTERNAL_COMPARE.md`（curated copy） |
| R30 baseline proof | — (來源在 Traing_Progress/) | `docs/evidence/baseline/ROUND30_EXTERNAL_COMPARE.md`（curated copy） |

**規則**：
- `Experiments/*/reports/` 是所有實驗報告的**唯一可編輯位置**
- `docs/evidence/` 是 curated copy / mirror，從 canonical source 複製而來
- 如果要修改 evidence 層的內容，先改 canonical source，再更新 mirror
- `docs/evidence/` 裡的 R30/R31 檔案是從 `Traing_Progress/` 複製的歷史 curated copy，原始來源不在 Experiments/

### 治理文件

| 文件 | 角色 | 編輯規則 |
|------|------|---------|
| `ESTIMATOR_POLICY.json` | Machine-readable baseline truth | 直接編輯 |
| `PROJECT_CURRENT_STATE.md` | Human-readable current state | 直接編輯 |
| `PROJECT_SESSION_CONTINUITY.md` | Cross-session handoff | 直接編輯 |
| `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md` | Stable rules | 直接編輯 |
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
