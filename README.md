# GMM_2_Final

## Canonical Reading Order

新接手時，只看這四份：

1. `PROJECT_SESSION_CONTINUITY.md`
2. `PROJECT_CURRENT_STATE.md`
3. `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md`
4. `PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md`（只有需要完整歷史時再看）

定位規則：

- 想快速接手：看 `PROJECT_SESSION_CONTINUITY.md`
- 想知道現在真相：看 `PROJECT_CURRENT_STATE.md`
- 想知道穩定規則：看 `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md`
- 想補完整歷史：最後看 `PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md`

## One-Screen Snapshot

- production baseline 仍是 `Round30 / r30_b1_dironly`
- `Round32` 已切到 `Experiments/R32Sandbox/`
- `Round32` internal winner `r32_real_eq_finetune` 已完成 external compare，結論是 **FAIL**
- 若要續做 `R32`，下一步必須是新的 sandbox branch / 新機制，不是延用這個 winner

## Project Goal

這不是一般影像增強專案。

真正目標是：

- 對 annulus 邊界做可定位的幾何重建
- 讓固定 external GMF 在不同位移尺度下都能穩定定位

工程上真正優化的不是「看起來更銳利」，而是 **whole-annulus geometry 是否更對 external GMF 友善**。

## Root Structure

```text
D:\GMM_2_Final\
├── README.md
├── PROJECT_SESSION_CONTINUITY.md
├── PROJECT_CURRENT_STATE.md
├── PROJECT_ARCHITECTURE_AND_DECISION_MAP.md
├── PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md
├── PROJECT_DOCUMENT_INDEX.md
├── ESTIMATOR_POLICY.json
├── Model\
├── Training_Data\
├── Traing_Progress\
├── PSF_Fitting\
├── Tools\
├── Experiments\
├── Project_Archive\
├── _deployment_package\
└── Trash_Archive\
```

## Directory Roles

- `Model\`
  shared stable workflow 的訓練 / 推論 / longrun / audit 腳本
- `Training_Data\`
  訓練、sequence、real-image 資料
- `Traing_Progress\`
  shared mainline 的正式 round artifact / report / checkpoint / log
- `Experiments\R32Sandbox\`
  `Round32` 專用 sandbox；訓練、audit、runtime、external compare 都在這裡收斂
- `PSF_Fitting\`
  PSF 擬合與物理先驗流程
- `Tools\`
  shared watcher / helper scripts
- `Project_Archive\`
  非 current truth 的 archive / maintenance artifact

## Current Workflow Boundaries

- root shared 主線不再繼續吸收 `R32` 專用 loader / audit / launcher / monitor
- `R32` 專用執行面以 `Experiments\R32Sandbox\` 為 canonical surface
- root `000_LONGRUN_ROUND32_STATUS.*` 只保留為 legacy bridge，不再是長期 canonical runtime state
- `Traing_Progress\organized_YYYYMMDD\roundNN\` 仍是 shared mainline 的正式 round 組織入口

## Maintenance Rules

1. `PROJECT_SESSION_CONTINUITY.md` 只做跨入口 handoff
2. `PROJECT_CURRENT_STATE.md` 只寫現在真相與下一個決策邊界
3. `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md` 只寫穩定架構與決策規則
4. `PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md` 只保留完整歷史與研究反省
5. `PROJECT_DOCUMENT_INDEX.md` 只做文件分工索引
6. shared mainline 與 sandbox 分流後，不把 `R32` 專用 runtime 細節再塞回 root shared 主線

## GitHub Repository Scope

這個 GitHub 倉庫是**研究程式碼與正式文件的治理面**，不是磁碟內容的完整鏡像。

會被追蹤進 Git 的內容：

- root 正式文件與 policy
- `Model\`
- `Tools\` 中的腳本、設定與說明
- `PSF_Fitting\`
- `Experiments\R32Sandbox\` 中的程式碼、README、runtime status、light reports、manifests

不會被追蹤進 Git 的內容：

- `Traing_Progress\`
- `Training_Data\`
- `_deployment_package\`
- checkpoints / weights / artifacts / reconstructions / raw GMF dumps / runtime logs
- local backup、portable runtime、editor state

原則很簡單：可以重現、可外部保存、體積過大、或不適合進 code review 的內容，都不進 Git history。

## Branch Strategy

這個 repo 使用混合式 branch 策略：

- `main`
  - 當前整理後的 shared mainline
- `baseline/*`
  - 正式 production baseline
- `reconstructed/*`
  - 依正式文件重建的高價值歷史節點
- `research/*`
  - 有研究價值但不冒充原始 git 歷史的語意分支
- `sandbox/*`
  - 已隔離的實驗面，例如 `R32Sandbox`

重建規則：

- 若 branch 是 reconstructed，必須明確標示 reconstructed
- 若 branch 是 semantic / research，也必須明確標示它不是原始歷史快照
- 本 repo 不會假造不存在的原始 git 歷史

詳見 `REPO_GOVERNANCE.md`。
