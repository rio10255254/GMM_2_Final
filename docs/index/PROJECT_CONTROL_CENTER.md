# Project Control Center / 專案控制中心

Last updated: 2026-04-13

這份文件定義專案的**官方控制入口**。  
It defines the project's **official control entry**.

它的工作不是發明新的真相，而是把既有正式真相、架構邊界、主要入口、已知風險、與整體健康整理到同一個可讀面。  
It does not create a new truth plane. It organizes the existing truth, architecture boundaries, entrypoints, known risks, and overall health into one readable surface.

## 它是什麼 / What It Is

- 官方控制命令：`python Tools/project_control_center.py`
- 官方導覽頁：本文件
- 預設行為：先看總覽，不直接跑重檢查
- JSON 輸出是衍生快照，不是新的 source of truth

## 它不是什麼 / What It Is Not

- 它不是新的真相來源
- 它不取代 `ESTIMATOR_POLICY.json`
- 它不取代 `PROJECT_CURRENT_STATE.md`
- 它不取代 `PROJECT_SESSION_CONTINUITY.md`
- 它不直接啟動訓練、推論或實驗

## 怎麼用 / How To Use It

```bash
# 看專案總覽（預設）
python Tools/project_control_center.py

# 看目前正式真相與證據入口
python Tools/project_control_center.py --view truth

# 看架構邊界
python Tools/project_control_center.py --view architecture

# 看主要入口
python Tools/project_control_center.py --view entrypoints

# 看已知風險
python Tools/project_control_center.py --view risks

# 跑日常健康檢查（官方標準）
python Tools/project_control_center.py --view health

# 跑快速健康檢查
python Tools/project_control_center.py --view health --health-level quick

# 跑深檢（含 MATLAB，本機用）
python Tools/project_control_center.py --view health --health-level deep

# 只看某些模組
python Tools/project_control_center.py --view health --module docs --module python

# 輸出機器可讀 JSON
python Tools/project_control_center.py --view overview --format json
```

## 視圖 / Views

- `overview`：正式狀態、架構摘要、真相入口、主要入口、已知風險、輕量健康摘要
- `truth`：正式 baseline、approved alternates、open side track、真相來源、證據入口
- `architecture`：主線、side track、關閉沙盒、歷史封存、邊界提醒
- `entrypoints`：主要訓練、推論、TTA、PSF、分析、導覽入口
- `risks`：目前仍需要注意的高價值風險
- `health`：白名單健康檢查

## 健康檢查層級 / Health Levels

- `quick`
  - 文件真相一致性
  - 主要入口存在性
  - 主線三個 Python 入口 `--help`
  - tracked 工作區狀態
- `standard`
  - `quick` 全部內容
  - 結構檢查
  - 穩定白名單 Python 測試
  - 語法可載入檢查
- `deep`
  - `standard` 全部內容
  - MATLAB 煙霧檢查
  - ValidationLab 輸出會改走臨時位置，不覆寫正式摘要

## 正式閱讀順序 / Formal Reading Order

1. `PROJECT_SESSION_CONTINUITY.md`
2. `PROJECT_CURRENT_STATE.md`
3. `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md`
4. `ESTIMATOR_POLICY.json`
5. `docs/evidence/EVIDENCE_MAP.md`

如果你只想先看全貌，就先跑控制中心；如果你要修改正式結論，還是回到上述正式真相文件。  
If you only need the whole picture, start with the control center. If you need to change formal conclusions, go back to the source-of-truth files above.

## 邊界提醒 / Boundary Notes

- legacy runtime 快照已封存到 `docs/archive/legacy_runtime_status/`
- `docs/runtime/legacy/` 現在只保留搬遷說明
- 根目錄裸跑總測試不是官方健康判準
- `deep` 是本機深檢，不是 CI 的常規責任
