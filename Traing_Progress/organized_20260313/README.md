# organized_20260313 — Round 16 / 17 / 18 / 19 實驗記錄

這個目錄包含 2026-03-12 ~ 2026-03-13 的四輪主要實驗。
命名規則統一使用 `organized_YYYYMMDD/roundNN/` 階層，避免再次回到 `organized_rNN` 或 root-level `training_progress_*` 散落的結構。

另外保留 `root_status_legacy/`，用來保存當時 round-level 與 root-level longrun 狀態快照。

---

## 結構規格

每個 round 目錄應維持以下結構：

```text
roundNN/
├── selected/
│   ├── runs/           ← 選定 candidate 的正式 training_progress_* 目錄
│   └── reports/        ← multiscale summary + checkpoint audit
├── archive/
│   ├── runs/           ← 未選中的候選 run
│   ├── audit_runs/     ← universal / checkpoint audit 產物
│   ├── resume_cache/   ← round resume_init checkpoint
│   ├── logs/           ← smoke / 啟動失敗 / 額外 debug log
│   └── status_legacy/  ← round-local 狀態檔副本
├── pending/
│   └── logs/           ← 當輪 longrun 主 log
└── external_validation/ ← 外部重建 / GMF 驗證資料（若有）
```

---

## 各 round 摘要

### Round 16 — EDGEFIT（2026-03-12）
- 核心機制：引入 `edge_centroid` 幾何估計方法（相對 r15 的 algebraic_fit）
- 部署選定：`r16_edge_highcenter`
- 主要結果：`center_err` 顯著下降，但 `step_err` 退步到超過硬閾值
- 角色定位：證明 `edge_centroid` 比舊路線更適合當後續主線

### Round 17 — STEPFIX（2026-03-13 上午）
- 核心機制：新增 `SEQ_STEP_MAG_WEIGHT`，直接修 step magnitude
- 部署選定：`r17_ec_stepmag`
- 主要結果：`step_err` 修回安全範圍，同時把 `0.8px center_err` 壓到歷史最低附近
- 角色定位：目前最乾淨的 `0.8px center_err` 基線來源

### Round 18 — CENTERPUSH（2026-03-13 下午）— **目前採用**
- 核心機制：延續 round17，進一步提高 center 相關權重
- 部署選定：`r18_ec_highcenter`
- 主要結果：仍未突破 `0.8px center_err ≈ 0.85` 平台，但整體 deploy score 最穩
- 角色定位：目前正式採用的內部最佳基線

### Round 19 — ABSANCHOR（2026-03-13 晚間）— **已完成，不採用**
- 核心機制：新增 `SEQ_ABS_CENTER_WEIGHT` / `abs_center`，直接對準絕對中心位置誤差
- 候選：
  - `r19_abs_anchor`
  - `r19_abs_strong`
  - `r19_af_abs`
  - `r19_abs_only`
- 選定候選：`r19_abs_anchor`
- 主要結果：
  - `0.8px center_err ≈ 0.8560`
  - `0.8px step_err ≈ 0.2789`
  - `8px step_err ≈ 0.0289`
- 判讀：
  - `step_err` 依舊安全
  - `0.8px center_err` 沒有突破平台
  - `abs_center` 這個注入方式目前未形成足夠有效的新梯度方向
- 角色定位：已完成的否定性驗證，說明「直接加目前這版 absolute-center anchor」不足以解決主瓶頸

---

## 目前採用

目前正式採用模型仍是：

- **Round 18 / `r18_ec_highcenter`**
- 快速入口：
  `D:\GMM_2_Final\Traing_Progress\organized_20260313\round18\selected\current_centerpush_seed.json`

Round 19 已完成，但**未通過 internal gate**，因此不升級 current adopted model，也沒有進 external GMF。

---

## 目前最重要的判讀

從 Round 16 → 19 的演化可以濃縮成一句話：

- `8px` 與 `step_err` 已經大致被控制住
- 真正沒解掉的是 `0.8px / 0.1um` 的 annulus **絕對中心穩定性**

所以後續若再開新 round，應繼續以 `0.8px center_err` 為 primary gate，而不是回去做泛用 universal sweep。

---

## 操作原則

- 不再把新的 `training_progress_*` 留在 `Traing_Progress` 根目錄
- 不再新增 `organized_rNN` 這類分裂命名
- 每個 round 完成後，要立即把：
  - selected runs
  - archive runs
  - audit runs
  - logs
  - current_*_seed.json
  收回 round 目錄內

這樣之後才不會再需要二次大型清理。

---

## Legacy Governance Entry Points

若要安全回頭操作這批歷史 round，請另外使用：

1. `MANIFEST.md`
2. `..\..\docs\index\LEGACY_ROUNDS_OPERATIONS.md`
3. `root_status_legacy\README.md`
4. `round16\README.md` 到 `round19\README.md`

這些治理檔是後補的導引層，不取代原始 round 報告與 status 快照。
